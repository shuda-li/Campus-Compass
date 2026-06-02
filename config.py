import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
# 默认使用 DeepSeek API（OpenAI 兼容协议，前缀缓存友好）
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "rooms.db")
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "data", "templates.json")
