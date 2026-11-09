"""run.py - Cross-Platform FastAPI & Workstation Server Launcher."""

from __future__ import annotations

import uvicorn
from backend.core.config import HOST, PORT

if __name__ == "__main__":
    print(f"Starting LocalOSINT v3.0 Global Intelligence Command Centre on http://{HOST}:{PORT}")
    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )
