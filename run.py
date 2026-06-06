"""
Campus Compass 一键启动脚本
自动检查依赖 → 安装缺失 → 启动服务 → 打开浏览器
"""

import subprocess
import sys
import os
import webbrowser
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = os.path.join(PROJECT_DIR, "requirements.txt")


def ensure_utf8():
    """Windows 终端 UTF-8 乱码修复。"""
    try:
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr.encoding != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def check_deps():
    """检查所有依赖是否已安装，缺失则自动安装。"""
    # 包名 → import 名映射
    import_map = {
        "python-dotenv": "dotenv",
        "python-docx": "docx",
        "lxml": "lxml",
        "flask": "flask",
        "requests": "requests",
    }

    missing = []
    try:
        with open(REQUIREMENTS, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                pkg_base = line.split(">=")[0].split("==")[0].split("<")[0].strip()
                import_name = import_map.get(pkg_base, pkg_base.replace("-", "_").lower())
                try:
                    __import__(import_name)
                except ImportError:
                    missing.append(line)
    except FileNotFoundError:
        print("[run] requirements.txt 未找到，跳过依赖检查")
        return

    if not missing:
        print("[run] 所有依赖已就绪 ✓")
        return

    print(f"[run] 检测到 {len(missing)} 个依赖缺失，正在自动安装...")
    print(f"[run] pip install {' '.join(missing)}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q"] + missing,
            cwd=PROJECT_DIR,
        )
        print("[run] 依赖安装完成 ✓")
    except subprocess.CalledProcessError as e:
        print(f"[run] 依赖安装失败！请手动执行: pip install -r requirements.txt")
        print(f"[run] 错误: {e}")
        sys.exit(1)


def main():
    ensure_utf8()

    print("=" * 50)
    print("  Campus Compass · 校园活动策划助手")
    print("  Star Rail UI · DeepSeek 驱动")
    print("=" * 50)
    print()

    # 切换到项目目录
    os.chdir(PROJECT_DIR)

    # 检查依赖
    check_deps()
    print()

    # 启动 Flask
    port = 5000
    print(f"[run] 正在启动服务...")
    print(f"[run] 浏览器即将打开 http://localhost:{port}")
    print(f"[run] 按 Ctrl+C 停止")
    print()

    # 延迟打开浏览器（等 Flask 绑定端口）
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动 Flask（不启用 debug 重载）
    from web.app import app
    app.run(debug=False, port=port)


if __name__ == "__main__":
    main()
