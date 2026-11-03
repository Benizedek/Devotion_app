"""Settings, read once from environment variables. Defaults suit running on your own computer.

    HOST            address to listen on            (default 127.0.0.1, this computer only)
    PORT            port to listen on               (default 8000)
    SECURE_COOKIES  set to 1 behind HTTPS in production
    DEVOTION_DB     path to the SQLite file         (default data/devotion.db)
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # the project folder
FRONTEND_DIR = ROOT / "frontend"

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
SECURE_COOKIES = os.environ.get("SECURE_COOKIES") == "1"
DB_PATH = Path(os.environ.get("DEVOTION_DB", ROOT / "data" / "devotion.db"))

MAX_BODY = 64 * 1024                                   # largest JSON request accepted, in bytes
