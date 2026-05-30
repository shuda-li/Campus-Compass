import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 重新加载环境变量
from dotenv import load_dotenv
load_dotenv(override=True)

from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL, TAVILY_API_KEY

print("===== 环境配置 =====")
print(f"LLM Provider : 千问 3.5 Plus")
print(f"LLM API URL  : {LLM_API_URL}")
print(f"LLM Model    : {LLM_MODEL}")
print(f"LLM API Key  : {LLM_API_KEY[:12]}...{LLM_API_KEY[-4:]}")
print(f"Tavily Key   : {'已配置' if TAVILY_API_KEY else '[未配置]'}")

print("\n===== 1. 基础连通性 =====")
try:
    from agent.llm import complete
    content = complete("回复'千问连通成功'", system="简短回复，不加标点。", temperature=0.1, max_tokens=20)
    print(f"✅ {content.strip()}")
except Exception as e:
    print(f"❌ {e}")

print("\n===== 2. 主题扩展能力 =====")
try:
    from agent.llm import expand_topic
    result = expand_topic("MBTI")
    print(f"✅ '{result}'")
except Exception as e:
    print(f"❌ {e}")

print("\n===== 3. MCP搜索 =====")
try:
    from agent.mcp.tavily_search import search_web
    import json
    data = json.loads(search_web("千问大模型 校园活动", max_results=1))
    ok = "✅" if data.get("ok") else "⚠️"
    print(f"{ok} {data.get('answer', '')[:80]}...")
except Exception as e:
    print(f"❌ {e}")