"""Run the FastAPI server directly."""
import sys, os
sys.dont_write_bytecode = True

PORT = int(os.environ.get("PORT", 8137))

# Import app directly first (ensures fresh imports)
from app.main import app
import uvicorn

uvicorn.run(app, host="0.0.0.0", port=PORT, reload=False)
