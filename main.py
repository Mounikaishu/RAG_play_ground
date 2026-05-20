"""
Entry point for PlaceAI application.
Exposes the FastAPI app from the backend directory and ensures backend paths are on the Python system path.
"""
import sys
import os

# Put backend directory at the front of sys.path so backend modules can be imported directly
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Now we can import the FastAPI application cleanly
from backend.main import app
