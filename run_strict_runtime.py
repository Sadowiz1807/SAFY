from __future__ import annotations

# Development harness only. Official production path is:
# python -m Apps.Api.safy_api.cli run --port 8000
from Apps.Api.safy_api.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
