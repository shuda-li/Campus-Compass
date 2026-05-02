import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from engine.workflow import run_workflow

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"reply": "请输入您的活动想法~", "success": False})

    try:
        result = run_workflow(user_msg)
        return jsonify({"reply": result, "success": True})
    except Exception as e:
        return jsonify({
            "reply": f"<div class='bg-red-900/20 border border-red-500/20 text-red-300 px-5 py-3 rounded-2xl text-sm'>出错了: {str(e)}</div>",
            "success": False,
        })


if __name__ == "__main__":
    print("=" * 50)
    print("  🎓 Campus Compass 校园活动策划助手")
    print("  浏览器打开: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
