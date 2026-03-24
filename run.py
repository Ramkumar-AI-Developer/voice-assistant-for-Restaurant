"""
Start the server:

    python run.py

Or directly with uvicorn (recommended for production):

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,          # set False in production
        log_level="info",
        access_log=True,
    )
