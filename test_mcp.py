#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TAVILY_API_KEY
from agent.mcp.tavily_search import search_web, search_activity_trends, is_available


def test_mcp_search():
    print("===== MCP 工具测试 =====")
    print(f"Tavily API Key 可用: {is_available()}")
    if not TAVILY_API_KEY:
        print("⚠️ Tavily API Key 未配置")
        return

    print("\n===== 测试 1: 搜索 '校园MBTI活动' =====")
    result = search_web("校园MBTI活动 创意 策划", max_results=3)
    print(result)

    print("\n===== 测试 2: 活动趋势搜索 '毕业季' =====")
    result2 = search_activity_trends("毕业季")
    print(result2)


if __name__ == "__main__":
    test_mcp_search()
