import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL, TAVILY_API_KEY

print("===== 环境配置检查 =====")
print(f"LLM Provider : DeepSeek")
print(f"LLM API URL  : {LLM_API_URL}")
print(f"LLM Model    : {LLM_MODEL}")
print(f"LLM API Key  : {LLM_API_KEY[:12]}...{LLM_API_KEY[-4:]}" if LLM_API_KEY else "[未配置]")
print(f"Tavily Key   : {'已配置' if TAVILY_API_KEY else '[未配置]'}")

print("\n===== 测试 DeepSeek 连通性 =====")
try:
    from agent.llm import complete
    content = complete("请回复'DeepSeek连通成功'，不要其他内容", system="你是简短回复助手。", temperature=0.1, max_tokens=20)
    if content:
        print(f"✅ 成功: {content.strip()}")
    else:
        print("❌ 返回为空")
except Exception as e:
    print(f"❌ 错误: {e}")

print("\n===== 测试 MCP 搜索 =====")
try:
    from agent.mcp.tavily_search import search_web
    result = search_web("校园活动策划 DeepSeek", max_results=1)
    import json
    data = json.loads(result)
    if data.get("ok"):
        print(f"✅ MCP搜索连通: {data.get('answer', '')[:60]}...")
    else:
        print(f"⚠️ MCP搜索: {data}")
except Exception as e:
    print(f"❌ MCP错误: {e}")