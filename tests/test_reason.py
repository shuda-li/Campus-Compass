import requests


def test_scenario(label: str, topic: str, participants: int):
    r = requests.post("http://localhost:5000/chat", json={"message": topic}).json()
    sid = r["session_id"]
    r = requests.post("http://localhost:5000/chat", json={"message": str(participants), "session_id": sid}).json()
    reply = r.get("reply", "")

    extract = ""
    for key in ["签到", "嘉宾", "比赛", "节目", "布展", "热身", "动手实践", "投票"]:
        if key in reply:
            extract += key + " "
    purpose = reply[reply.find("活动目的") : reply.find("活动目的") + 200] if "活动目的" in reply else ""

    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"  主题: {topic} | 人数: {participants}")
    print(f"  推理出的环节: {extract.strip()}")
    print(f"  目的片段: {purpose[:120]}...")


test_scenario("场景1: 分享类", "AI 时代的技术趋势分享会", 60)
test_scenario("场景2: 竞赛类", "大学生编程马拉松挑战赛", 80)
test_scenario("场景3: 演出类", "校园音乐节", 100)
test_scenario("场景4: 实践类", "手工烘焙体验工作坊", 30)
test_scenario("场景5: 展览类", "校园摄影作品展", 50)

print()
print("✅ 5 种场景全部测试完成")
