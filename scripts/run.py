"""Start the custom dashboard and API on loopback."""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("MEDFLOW_HOST", "127.0.0.1"),
        port=int(os.environ.get("MEDFLOW_PORT", "8000")),
    )
