"""Hugging Face Spaces entrypoint for Wulf Web Leader."""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ZeroGPU decorator for Hugging Face Free Tier
try:
    import spaces

    @spaces.GPU(duration=1)
    def _run_gpu():
        """Technical function required by Hugging Face ZeroGPU environment."""
        return "ready"
except (ImportError, Exception):
    def _run_gpu():
        return "ready"

from gradio import Server
from wulf_web_leader.web.app import app as fastapi_app

# Use Gradio Server to host custom FastAPI dashboard + ZeroGPU API
app = Server(title="Wulf Web Leader")

# Attach all FastAPI routes (dashboard /, /health, /api/*)
app.include_router(fastapi_app.router)

# Register @spaces.GPU function via @app.api so ZeroGPU detects it during startup
@app.api(name="healthcheck_gpu")
def healthcheck_gpu() -> str:
    return _run_gpu()

demo = app

if __name__ == "__main__":
    demo.launch(ssr_mode=False)
