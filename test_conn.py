import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(override=True)

from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL

print(f"Model : {LLM_MODEL}")
print(f"URL   : {LLM_API_URL}")
print(f"Key   : {LLM_API_KEY[:12]}...{LLM_API_KEY[-4:]}")

print("\n--- 测试连通 ---")
try:
    from agent.llm import complete
    r = complete("回复'ok'", system="简短回复。", temperature=0.1, max_tokens=10)
    print(f"✅ 连通: {r.strip()}")
except Exception as e:
    print(f"❌ {e}")
