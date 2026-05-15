"""Backend app package."""
from pathlib import Path

# Load environment variables from backend/.env at import time so any entrypoint
# (uvicorn, pytest, ad-hoc python -c, etc.) picks up secrets like GROQ_API_KEY.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass
