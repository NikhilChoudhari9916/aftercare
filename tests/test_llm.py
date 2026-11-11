import json

import anthropic
import httpx2
import pytest
from pydantic import BaseModel

from app.llm import (
    AnthropicLLM,
    LLMError,
    LLMOutputError,
    LLMRefused,
    LLMUnavailable,
    ToolCall,
    get_llm,
)


class Reading(BaseModel):
    name: str
    count: int


def message(content: list[dict], stop_reason: str = "end_turn") -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def text(value: str) -> dict:
    return {"type": "text", "text": value}


class Recorder:
    def __init__(self, response: httpx2.Response | Exception) -> None:
        self.response = response
        self.bodies: list[dict] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.bodies.append(json.loads(request.content))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def llm_with(recorder: Recorder) -> AnthropicLLM:
    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(recorder)),
    )
    return AnthropicLLM("test-key", 5.0, client=client)


def ok(content: list[dict], stop_reason: str = "end_turn") -> Recorder:
    return Recorder(httpx2.Response(200, json=message(content, stop_reason)))


ASK = {
    "model": "claude-sonnet-5-5",
    "system": "Be brief.",
    "messages": [{"role": "user", "content": "hi"}],
}


def test_a_text_reply_comes_back_and_the_request_is_shaped_correctly():
    recorder = ok([text("Hello there.")])
    reply = llm_with(recorder).complete(**ASK, effort="low", max_tokens=300)

    assert reply.text == "Hello there."
    assert reply.tool_calls == []
    assert reply.stop_reason == "end_turn"
    body = recorder.bodies[0]
    assert body["model"] == "claude-sonnet-5-5"
    assert body["system"] == "Be brief."
    assert body["max_tokens"] == 300
    assert body["output_config"] == {"effort": "low"}
    assert "temperature" not in body  # rejected by the current models
    assert "tools" not in body


def test_tool_calls_are_parsed_and_the_raw_blocks_are_kept_for_the_next_turn():
    blocks = [
        text("Let me check."),
        {"type": "tool_use", "id": "toolu_1", "name": "lookup", "input": {"drug": "lisinopril"}},
    ]
    recorder = ok(blocks, stop_reason="tool_use")
    tools = [{"name": "lookup", "description": "d", "input_schema": {"type": "object"}}]

    reply = llm_with(recorder).complete(**ASK, tools=tools)

    assert reply.tool_calls == [ToolCall("toolu_1", "lookup", {"drug": "lisinopril"})]
    assert reply.text == "Let me check."
    assert [block.type for block in reply.content] == ["text", "tool_use"]
    assert recorder.bodies[0]["tools"] == tools


def test_a_refusal_is_reported_as_a_refusal():
    with pytest.raises(LLMRefused):
        llm_with(ok([text("")], stop_reason="refusal")).complete(**ASK)


def test_a_reply_cut_off_at_the_token_limit_is_an_error():
    with pytest.raises(LLMOutputError):
        llm_with(ok([text("half an ans")], stop_reason="max_tokens")).complete(**ASK)


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(429, json={"type": "error", "error": {"type": "rate_limit_error"}}),
        httpx2.Response(500, json={"type": "error", "error": {"type": "api_error"}}),
        httpx2.Response(529, json={"type": "error", "error": {"type": "overloaded_error"}}),
        httpx2.ConnectError("refused"),
        httpx2.ReadTimeout("slow"),
    ],
)
def test_outages_timeouts_and_rate_limits_are_unavailable(response):
    with pytest.raises(LLMUnavailable):
        llm_with(Recorder(response)).complete(**ASK)


def test_a_rejected_request_is_a_plain_error_not_an_outage():
    recorder = Recorder(
        httpx2.Response(400, json={"type": "error", "error": {"type": "invalid_request_error"}})
    )
    with pytest.raises(LLMError) as raised:
        llm_with(recorder).complete(**ASK)
    assert not isinstance(raised.value, LLMUnavailable)


def test_extract_returns_a_validated_model_and_sends_the_schema_and_effort():
    recorder = ok([text('{"name": "furosemide", "count": 2}')])

    result = llm_with(recorder).extract(
        model="claude-sonnet-5-5", system="Extract.", user="text", schema=Reading, effort="medium"
    )

    assert result == Reading(name="furosemide", count=2)
    body = recorder.bodies[0]
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["messages"] == [{"role": "user", "content": "text"}]


def test_extract_reports_unreadable_output():
    recorder = ok([text("not json at all")])
    with pytest.raises(LLMOutputError):
        llm_with(recorder).extract(
            model="claude-sonnet-5-5", system="Extract.", user="text", schema=Reading
        )


def test_without_an_api_key_there_is_no_llm(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(LLMUnavailable, match="ANTHROPIC_API_KEY"):
        get_llm()
