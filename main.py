from data.init_db import init_database
from engine.workflow import run_workflow


def main():
    print("=" * 50)
    print("  🎓 Campus Compass - 校园活动策划助手")
    print("=" * 50)
    print()

    init_database()

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
        result = run_workflow(user_input)
        print(result)
        print()


if __name__ == "__main__":
    main()
