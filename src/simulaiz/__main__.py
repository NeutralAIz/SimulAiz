"""Entry point for the SimulAiz runtime container."""

from __future__ import annotations

import os
import threading

import uvicorn

from .agent import start_background_agent
from .web import app as fastapi_app


def main() -> None:
    """Run the web UI + API and optionally start the background agent."""
    # Start background agent if configured
    start_background_agent()

    host = os.getenv("SIMULAIZ_HOST", "0.0.0.0")
    port = int(os.getenv("SIMULAIZ_PORT", "8000"))
    log_level = os.getenv("SIMULAIZ_LOG_LEVEL", "info").lower()

    # Run FastAPI via Uvicorn
    uvicorn.run(fastapi_app, host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
