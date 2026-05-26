import requests

print("=" * 50)
print(" Campus Compass - 3步交互流程测试")
print("=" * 50)

# Step 1: 输入主题
r = requests.post("http://localhost:5000/chat", json={"message": "科技创新活动"}).json()
sid = r.get("session_id", "")
print(f"\n[Step 1] 输入主题 '科技创新活动'")
print(f"  session: {sid}")
print(f"  success: {r['success']}")
print(f"  回复: {r['reply'][:80]}...")

# Step 2: 输入人数
r = requests.post("http://localhost:5000/chat", json={"message": "80", "session_id": sid}).json()
print(f"\n[Step 2] 输入人数 '80'")
print(f"  success: {r['success']}")
reply = r.get("reply", "")
checks = {
    "活动目的": "activity_purpose" in reply or "活动目的" in reply,
    "活动内容": "活动内容" in reply,
    "活动物资": "活动物资" in reply,
    "推荐教室": "推荐教室" in reply,
    "主办单位": "主办单位" in reply,
    "XXX占位符": "XXX" in reply,
}
for k, v in checks.items():
    print(f"  包含{k}: {'✅' if v else '❌'}")
print(f"  回复长度: {len(reply)} 字符")

print()
all_pass = all(checks.values())
print(f"{'✅ 全部测试通过' if all_pass else '❌ 存在失败项'}")
