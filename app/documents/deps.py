from fastapi import HTTPException, Request

from app.jobs.runner import JobRunner
from app.llm import LLM, LLMUnavailable, get_llm


def get_job_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


def get_llm_or_503() -> LLM:
    try:
        return get_llm()
    except LLMUnavailable as error:
        raise HTTPException(
            status_code=503, detail="AfterCare's AI service is not set up on this server."
        ) from error
