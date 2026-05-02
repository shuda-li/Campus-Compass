import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "rooms.db")
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "data", "templates.json")
