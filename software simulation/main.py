"""
Vercel Services Entrypoint for FastAPI Backend.
Exposes the authoritative FastAPI app instance from backend.api.main.
"""
import sys
import os

# Ensure the root of software simulation is on sys.path
sys_path_root = os.path.dirname(os.path.abspath(__file__))
if sys_path_root not in sys.path:
    sys.path.insert(0, sys_path_root)

from backend.api.main import app
