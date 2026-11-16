"""What the model was shown that it may cite, and what may justify a number or a time.

Tools return passages and labels. This keeps them by ID (D1, L1, ...) so the validators can
check that every cited ID was really retrieved and that a dose, time or name in the answer is
backed by something. It also remembers where each source came from, for the citation tags.
"""

import json
from typing import Any

PAPERS = "paper"
LABEL = "label"


class SourceBook:
    def __init__(self) -> None:
        self.texts: dict[str, str] = {}  # id -> the words, for validate_answer(retrieved=...)
        self.meta: dict[str, dict[str, Any]] = {}  # id -> where it came from, for the UI
        self.evidence: list[str] = []  # other text that may justify a time, such as the schedule
        self._label_ids: dict[str, str] = {}

    def add_tool_result(self, name: str, result: dict[str, Any]) -> dict[str, Any]:
        """Record a tool's result and return what to hand back to the model.

        A drug label comes back without an ID, so it is given one here (L1, L2, ...).
        """
        if not result.get("ok"):
            return result
        data = result.get("data", {})

        if name == "search_patient_document":
            for passage in data.get("passages", []):
                self.texts[passage["id"]] = passage["text"]
                self.meta[passage["id"]] = {
                    "kind": PAPERS,
                    "page": passage["page"],
                    "section": passage["section"],
                }
            return result

        if name == "search_fda_label":
            if not data.get("found"):
                return result
            key = data["medicine"].casefold()
            label_id = self._label_ids.get(key)
            if label_id is None:
                label_id = f"L{len(self._label_ids) + 1}"
                self._label_ids[key] = label_id
                parts = [data.get(k) for k in ("purpose", "warnings", "boxed_warning")]
                self.texts[label_id] = " ".join(part for part in parts if part)
                self.meta[label_id] = {"kind": LABEL, "page": None, "medicine": data["medicine"]}
            return {**result, "data": {**data, "id": label_id}}

        if name in ("get_schedule", "lookup_rxnorm"):
            self.evidence.append(json.dumps(data))
        return result
