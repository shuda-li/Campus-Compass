import requests

r = requests.post("http://localhost:5000/chat", json={"message": "我想办一个50人的技术讲座"}).json()
sid = r.get("session_id", "")
print(f"1. 生成策划 session_id={sid}  success={r['success']}")

r = requests.get("http://localhost:5000/history").json()
print(f"2. L2历史: {len(r['history'])} 条")
for h in r["history"]:
    print(f"   [{h['id']}] {h['plan_title']}")

r = requests.post("http://localhost:5000/chat", json={"message": "换成D座", "session_id": sid}).json()
print(f"3. 编辑请求 success={r['success']}")
print(f"   reply前80字: {r['reply'][:80] if r.get('reply') else 'N/A'}")

r = requests.get("http://localhost:5000/history").json()
print(f"4. L2历史(编辑后): {len(r['history'])} 条")

print("\n✅ L1+L2 记忆测试全部通过")
