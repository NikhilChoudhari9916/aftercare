import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Request

from ui.api_client import COOKIE_NAME, BackendClient

# ui/ never imports from app/, so it reads the few settings it needs itself. The .env file
# is loaded here, before anything reads the environment.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")

backend = BackendClient(BACKEND_URL)


def session_token(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)
