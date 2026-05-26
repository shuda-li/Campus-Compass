from data.init_db import init_database
from agent.agent_loop import run_agent


def main():
    print("=" * 50)
    print("  🎓 Campus Compass - 校园活动策划 Agent")
    print("  🧠 LLM 驱动 · 工具调用 · 闭环决策")
    print("=" * 50)
    print()

    init_database()

    if not __import__("config").LLM_API_KEY:
        print("⚠ 未配置 LLM API Key，使用确定性流水线模式")
    else:
        print("✅ LLM 已配置，Agent 自主决策模式")
    print()
    print("请输入活动想法（输入 q 退出）:")
    print()

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n下次再见！")
            break

        if not user_input:
            continue

        if user_input.lower() == "q":
            print("下次再见！")
            break

        print()
        result = run_agent(user_input)
        print(result)
        print()


if __name__ == "__main__":
    main()
