"""Run the real backend with a scripted fake model, so no Anthropic key (and no cost) is needed.

For local demos and UI work only. Whatever PDF you upload, the "model" answers with the
synthetic Patient 1 profile (6 medicines), so use the sample PDF in data/synthetic/.
It uses a throwaway database and file folder, never your real ones.

    python scripts/demo_backend.py      # then, in a second terminal: python -m ui.main

Put DEV_LOGIN=1 in your .env so the test-login buttons appear (see TEAM_SETUP.md).
"""

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Settings are read once, so these must be set before the app is imported.
scratch = Path(tempfile.mkdtemp(prefix="aftercare-demo-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(scratch / 'demo.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(scratch / "storage")
os.environ.setdefault("DEV_LOGIN", "1")

import uvicorn  # noqa: E402

from app.documents.deps import get_llm_or_503  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.fakes import FakeLLM  # noqa: E402
from tests.samples import patient1_profile  # noqa: E402

UPLOADS_BEFORE_RESTART = 50

llm = FakeLLM()
for _ in range(UPLOADS_BEFORE_RESTART):
    llm.queue_extraction(patient1_profile())

app = create_app()
app.dependency_overrides[get_llm_or_503] = lambda: llm

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
