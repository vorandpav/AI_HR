# tg_bot/config.py
import os
from dotenv import load_dotenv
load_dotenv()

API_TOKEN = os.getenv("TELEGRAM_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

if not API_TOKEN:
    raise RuntimeError("Set TELEGRAM_TOKEN in .env")
