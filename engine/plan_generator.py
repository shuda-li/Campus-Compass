import json
import re


def generate_plan(topic: str, participants: int, rooms: list, llm_call_fn=None) -> dict:
    """生成完整活动方案，LLM 优先，规则推理兜底"""
    if llm_call_fn:
        try:
            plan = llm_call_fn(topic, participants)
            if plan and plan.get("activity_content"):
                return plan
        except Exception as e:
            print(f"[PlanGen] LLM失败: {e}")

    return _reason_plan(topic, participants, rooms)


def _classify_topic(topic: str) -> str:
    """根据主题关键词推理活动类别"""
    topic_lower = topic.lower()

    rules = [
        ("竞赛", ["竞赛", "比赛", "大赛", "挑战赛", "马拉松", "PK", "对决", "选拔", "锦标赛", "争霸", "竞技"]),
        ("演出", ["晚会", "演出", "音乐", "歌唱", "舞蹈", "表演", "才艺", "乐器", "合唱", "乐队", "戏剧", "话剧", "相声", "小品", "魔术", "街舞"]),
        ("展览", ["展览", "展销", "展览会", "展示", "摄影展", "画展", "作品展", "博览会", "成果展", "设计展"]),
        ("实践", ["实践", "动手", "制作", "DIY", "手工", "烘焙", "实验", "实训", "操作", "搭建", "组装", "花艺", "编程", "开发", "hackathon", "黑客松"]),
        ("运动", ["体育", "运动", "篮球", "足球", "跑步", "健身", "瑜伽", "登山", "骑行", "游泳", "武术", "太极", "羽毛球", "乒乓球", "排球", "运动会"]),
        ("分享", ["分享", "讲座", "演讲", "论坛", "沙龙", "交流", "研讨", "工作坊", "workshop", "培训", "学习", "知识", "经验", "心得", "读书", "阅读", "学术", "报告", "技术", "科普"]),
    ]

    scores = {}
    for category, keywords in rules:
        score = 0
        for kw in keywords:
            if kw in topic:
                score += 1
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)
    return "分享"


def _generate_purpose(topic: str, category: str) -> str:
    """根据类别推理活动目的（200-300字）"""
    templates = {
        "分享": (
            f'本次活动以"{topic}"为核心主题，旨在搭建一个开放、包容的校园知识交流平台。'
            f'通过邀请行业专家与资深实践者进行深度分享，帮助参与者系统了解相关领域的前沿动态、核心技术趋势及实际应用场景。'
            f'活动鼓励跨学科、跨年级的思想碰撞与经验交流，激发学生的学术热情与创新意识，拓宽知识视野。'
            f'同时，活动致力于营造"以学促思、以思促行"的校园学习文化，为同学们提供与同行交流、向榜样学习的宝贵机会，'
            f'助力个人成长与职业发展规划。'
        ),
        "竞赛": (
            f'本次活动以"{topic}"为竞技主题，旨在通过公平、公正、公开的竞赛机制，'
            f'充分挖掘和展示同学们在相关领域的专业才能与创新潜力。'
            f'竞赛不仅是一次技能的较量，更是团队协作、临场应变和抗压能力的综合考验。'
            f'活动通过设置合理的评分标准和奖项体系，激励参赛者全力以赴、追求卓越，同时为低年级同学树立学习榜样。'
            f'最终目标是选拔优秀人才、激发竞争意识，营造"比学赶帮超"的积极校园氛围，'
            f'推动相关学科在校园内的普及与发展。'
        ),
        "演出": (
            f'本次活动以"{topic}"为演出主题，旨在丰富校园文化生活，为拥有才艺的同学搭建展示自我、绽放光彩的舞台。'
            f'通过精心编排的节目演出，展现当代大学生的青春活力与艺术素养，增强集体凝聚力与归属感。'
            f'活动鼓励原创作品与创新表演形式，促进不同艺术门类之间的交流与融合，提升校园整体艺术氛围。'
            f'同时，活动也为观众提供了一场高品质的视听盛宴，让更多人感受艺术的魅力，'
            f'激发同学们对文化艺术的兴趣与热爱，营造"百花齐放、青春飞扬"的校园文化生态。'
        ),
        "展览": (
            f'本次活动以"{topic}"为展览主题，旨在集中展示同学们在相关领域的优秀创作成果，'
            f'搭建创作者与观众之间的直接交流桥梁。通过展品陈列、现场讲解和互动体验等多种形式，'
            f'让观众深入了解每件作品背后的创作理念、技术手段和艺术价值。'
            f'活动致力于促进校园文化交流与审美水平的提升，激励更多同学投身创作实践，'
            f'培养创新思维和动手能力。同时，展览也为不同专业背景的同学提供了跨学科交流的机会，'
            f'推动校园文化多元化发展，营造"人人参与、人人创造"的良好氛围。'
        ),
        "实践": (
            f'本次活动以"{topic}"为实践主题，旨在将理论知识与动手操作紧密结合，'
            f'通过"做中学、学中做"的方式，提升同学们的工程思维、动手能力和问题解决能力。'
            f'活动采用分阶段指导与自主实践相结合的模式，让参与者在专业指导下逐步掌握核心操作技能，'
            f'并鼓励团队协作与创新探索。最终目标是让每位参与者都能亲手完成一件作品或达成一个实践目标，'
            f'从中获得成就感与自信心。活动同时致力于打破"重理论轻实践"的传统观念，'
            f'营造"学以致用、知行合一"的校园实践文化。'
        ),
        "运动": (
            f'本次活动以"{topic}"为运动主题，旨在倡导积极健康的生活方式，'
            f'引导同学们走出宿舍、走向运动场，在体育锻炼中增强体魄、释放压力、享受快乐。'
            f'活动通过趣味性与竞技性相结合的项目设置，让不同运动水平的同学都能找到参与感和成就感。'
            f'同时，团队项目培养协作精神和集体荣誉感，个人项目锻炼意志品质和心理素质。'
            f'活动致力于营造"人人爱运动、班班有活力"的校园体育文化，'
            f'让运动成为校园生活中不可或缺的精彩部分。'
        ),
    }
    return templates.get(category, templates["分享"])


def _generate_activities(topic: str, category: str, participants: int) -> list:
    """根据不同类别推理不同的活动流程"""
    topic_short = topic[:15]

    base_flow = {
        "分享": [
            ("签到入场", "20分钟",
             "参与者签到，领取活动议程和反馈表，自由交流暖场。",
             "各位同学请到签到处登记，领取资料后可以先自由交流。",
             "自由交流"),
            ("开场致辞", "10分钟",
             "主持人介绍活动背景和流程，欢迎到场嘉宾。",
             f'欢迎大家来到今天的"{topic_short}"活动，让我们一起度过充实而有意义的时光！',
             "主持人引导"),
            ("嘉宾分享", "45分钟",
             f'邀请嘉宾围绕"{topic}"进行主题演讲，分享实践经验与行业洞察。',
             "接下来有请今天的分享嘉宾，大家掌声欢迎！",
             "问答互动"),
            ("互动讨论", "30分钟",
             "参与者分组讨论，结合自身经历提出问题与见解，嘉宾巡回解答。",
             "现在进入互动环节，请大家分成4-6人小组，围绕刚才的内容展开讨论。",
             "小组讨论、嘉宾答疑"),
            ("总结与自由交流", "15分钟",
             "主持人总结要点，颁发嘉宾纪念品，参与者自由交流与合影。",
             "感谢嘉宾的精彩分享，也感谢大家的积极参与，让我们合影留念！",
             "合影留念"),
        ],
        "竞赛": [
            ("选手签到与抽签", "30分钟",
             "参赛选手签到确认身份，进行比赛顺序抽签，领取参赛证和规则说明。",
             "请各位选手到签到处确认信息并抽签，比赛将于15分钟后正式开始。",
             "自主签到"),
            ("开幕式", "15分钟",
             "主持人介绍比赛规则、评委阵容和评分标准，选手代表宣誓。",
             f'欢迎来到"{topic_short}"的现场！让我们共同见证精彩对决。',
             "主持人引导"),
            ("正式比赛", "90分钟",
             f'选手按抽签顺序进行"{topic}"主题竞赛，评委根据评分标准打分。',
             "接下来有请第一位选手登场，让我们拭目以待！",
             "现场竞技、评委打分"),
            ("评委点评与颁奖", "20分钟",
             "评委代表对整体表现进行点评，公布名次并颁发奖项。",
             "感谢所有选手的精彩表现，现在请评委代表进行点评……",
             "点评互动、颁奖仪式"),
            ("合影与闭幕", "10分钟",
             "全体参赛选手、评委和工作人员合影留念。",
             "感谢大家的辛勤付出，让我们明年再见！",
             "合影留念"),
        ],
        "演出": [
            ("观众入场", "30分钟",
             "观众凭票/邀请函入场，工作人员引导入座，发放节目单。",
             "各位观众请凭票入场，按指引入座，演出即将开始。",
             "有序入场"),
            ("开场表演与致辞", "15分钟",
             "暖场表演拉开序幕，主持人介绍演出背景和节目安排。",
             f'欢迎来到"{topic_short}"的演出现场，今夜星光灿烂！',
             "暖场表演"),
            ("节目表演（上半场）", "45分钟",
             f'按照节目单依次进行"{topic}"主题表演，涵盖多种艺术形式。',
             "接下来请欣赏第一个节目……",
             "舞台表演"),
            ("互动与中场休息", "15分钟",
             "观众投票/互动游戏环节，中场休息，工作人员准备下半场道具。",
             "现在是互动环节，请大家拿起手机为最喜欢的节目投票！",
             "观众投票、互动游戏"),
            ("节目表演（下半场）与谢幕", "45分钟",
             "下半场节目继续，全体演职人员谢幕，颁发最佳节目奖。",
             "感谢所有演职人员的倾情奉献，感谢观众朋友们的热情支持！",
             "舞台表演、谢幕"),
        ],
        "实践": [
            ("签到与分组", "15分钟",
             "参与者签到，按报名的兴趣方向分组，发放工具包和操作指南。",
             "请签到后到指定区域领取工具包，找到自己小组的位置。",
             "自由交流"),
            ("指导讲解", "20分钟",
             "指导老师讲解操作要点、安全规范和预期成果。",
             f'在正式开始动手之前，我先给大家讲解"{topic}"的操作流程和注意事项。',
             "讲解互动"),
            ("动手实践", "60分钟",
             f'各组按照指导进行"{topic}"的动手操作，指导老师巡回辅导。',
             "现在开始动手操作！有任何问题请举手，我们随时提供帮助。",
             "实践操作、小组协作"),
            ("成果展示与互评", "25分钟",
             "各组展示实践成果，相互观摩评价，指导老师点评。",
             "时间到！请各组派代表展示你们的成果，每组3分钟。",
             "展示交流、互评打分"),
            ("总结与表彰", "10分钟",
             "颁发最佳实践奖和最佳创意奖，全体合影。",
             "大家的作品都非常出色，让我们为彼此的创意鼓掌！",
             "合影留念"),
        ],
        "展览": [
            ("布展签到", "30分钟",
             "参展者签到并按编号布置展位，工作人员提供桌椅和展板。",
             "请参展同学到指定编号的展位进行布置，有问题请联系工作人员。",
             "自主布展"),
            ("开幕式", "15分钟",
             "主持人介绍展览主题和评选规则，宣布展览正式开始。",
             f'欢迎来到"{topic_short}"展览现场，让我们一同感受创意的魅力！',
             "主持人引导"),
            ("自由观展", "60分钟",
             f'观众自由参观各展位，与参展者交流讨论"{topic}"相关话题。',
             "展览正式开始，请大家自由参观，可以随时与参展者交流。",
             "自由参观、互动交流"),
            ("观众投票与评选", "20分钟",
             "观众投票评选最佳作品，评委进行专业评审。",
             "现在是投票环节，请为你最喜欢的作品投上一票！",
             "投票互动"),
            ("颁奖与闭幕", "10分钟",
             "公布评选结果，为获奖者颁发证书，全体合影。",
             "感谢所有参展者的精彩呈现，感谢观众的热情参与！",
             "合影留念"),
        ],
        "运动": [
            ("签到与热身", "20分钟",
             "参赛者签到，领取号码牌和活动T恤，在教练带领下进行热身。",
             "请大家签到后到热身区集合，我们进行赛前热身运动。",
             "集体热身"),
            ("开幕式与规则说明", "10分钟",
             "主持人介绍运动项目、比赛规则和安全注意事项。",
             f'欢迎参加"{topic_short}"，请大家注意安全，友谊第一比赛第二！',
             "主持人引导"),
            ("正式比赛/活动", "60分钟",
             f'按照比赛规则进行"{topic}"的正式比赛或体育活动。',
             "比赛正式开始！大家加油！",
             "竞技比赛、团队协作"),
            ("趣味挑战", "20分钟",
             "设置趣味关卡或挑战项目，增加活动趣味性和参与度。",
             "正式比赛结束！接下来是趣味挑战环节，人人都能参与！",
             "趣味互动"),
            ("颁奖与合影", "10分钟",
             "公布成绩，为优胜者颁发奖牌和奖品，全体合影。",
             "恭喜各位优胜者！感谢所有人的热情参与！",
             "合影留念"),
        ],
    }

    flow = base_flow.get(category, base_flow["分享"])
    result = []
    for phase, duration, content, guide, interaction in flow:
        result.append({
            "phase": phase,
            "duration": duration,
            "content": content,
            "host_guide": guide,
            "interaction": interaction,
        })
    return result


def _generate_materials(topic: str, category: str, participants: int) -> list:
    """根据类别推理需要的物资"""
    common = [
        {"name": "签到表", "spec": "A4打印", "qty": "5张"},
        {"name": "饮用水", "spec": "瓶装550ml", "qty": f"{int(participants * 1.2)}瓶"},
    ]

    category_materials = {
        "分享": [
            {"name": "投影仪", "spec": "高清，支持HDMI", "qty": "1台"},
            {"name": "音响设备", "spec": "含无线话筒×2", "qty": "1套"},
            {"name": "翻页笔", "spec": "激光翻页", "qty": "1支"},
            {"name": "白板/写字板", "spec": "带白板笔", "qty": "1块"},
        ],
        "竞赛": [
            {"name": "投影仪", "spec": "高清，显示计时器", "qty": "1台"},
            {"name": "计时器", "spec": "大屏显示", "qty": "1个"},
            {"name": "评分表", "spec": "A4打印，含评分标准", "qty": f"{participants}份"},
            {"name": "号码牌/参赛证", "spec": "塑封卡片", "qty": f"{int(participants * 1.5)}个"},
            {"name": "证书/奖状", "spec": "A4，烫金字", "qty": "10份"},
        ],
        "演出": [
            {"name": "舞台灯光", "spec": "面光+追光+染色", "qty": "1套"},
            {"name": "专业音响", "spec": "含调音台+手持话筒×4", "qty": "1套"},
            {"name": "投影/背景屏", "spec": "LED背景屏或投影幕", "qty": "1块"},
            {"name": "节目单", "spec": "A4彩印", "qty": f"{participants}份"},
            {"name": "服装/道具", "spec": "根据节目需求", "qty": "若干"},
        ],
        "实践": [
            {"name": "工具包", "spec": "含基础工具", "qty": f"{int(participants / 4)}套"},
            {"name": "操作材料", "spec": "根据主题准备", "qty": "若干"},
            {"name": "安全手套", "spec": "均码", "qty": f"{participants}双"},
            {"name": "投影仪", "spec": "展示指导视频", "qty": "1台"},
            {"name": "成果展示台", "spec": "长桌", "qty": f"{int(participants / 8)}张"},
        ],
        "展览": [
            {"name": "展板/展架", "spec": "1.2m×0.9m，带挂钩", "qty": f"{int(participants / 4)}块"},
            {"name": "长桌", "spec": "1.8m", "qty": f"{int(participants / 4)}张"},
            {"name": "作品标签卡", "spec": "A5硬卡纸", "qty": f"{participants}张"},
            {"name": "投票箱", "spec": "带锁", "qty": "2个"},
            {"name": "选票", "spec": "A5纸，编号", "qty": f"{participants}张"},
        ],
        "运动": [
            {"name": "运动器材", "spec": "根据项目配置", "qty": "若干"},
            {"name": "号码牌/背心", "spec": "荧光色分队服", "qty": f"{participants}件"},
            {"name": "急救箱", "spec": "含创可贴/云南白药/冰袋", "qty": "2个"},
            {"name": "哨子/扩音器", "spec": "裁判用", "qty": "3个"},
            {"name": "饮用水", "spec": "桶装水+纸杯", "qty": f"{int(participants / 10)}桶"},
        ],
    }

    materials = category_materials.get(category, category_materials["分享"])
    return common + materials


def _reason_plan(topic: str, participants: int, rooms: list) -> dict:
    """Agent 自主推理：分析主题 → 归类 → 生成差异化方案"""
    category = _classify_topic(topic)
    purpose = _generate_purpose(topic, category)
    activities = _generate_activities(topic, category, participants)
    materials = _generate_materials(topic, category, participants)

    return {
        "activity_purpose": purpose,
        "activity_time": "待定（请根据实际安排填写）",
        "activity_topic": topic,
        "organizer": "待定（主办单位）",
        "host": "待定（承办单位）",
        "activity_content": activities,
        "activity_materials": materials,
    }


def build_plan_prompt(topic: str, participants: int) -> str:
    return f'''你是校园活动策划专家，请为主题"{topic}"生成完整的活动策划方案。

预计参与人数: {participants}人
活动场地: E教学楼

请严格按照以下JSON格式输出（只输出JSON，不要其他文字）:

{{
    "activity_purpose": "活动目的",
    "activity_time": "XXX",
    "activity_topic": "{topic}",
    "organizer": "XXX",
    "host": "XXX",
    "activity_content": [
        {{
            "phase": "环节名称（要贴合主题，不要用笼统说法）",
            "duration": "时长（如15分钟）",
            "content": "该环节的详细内容和执行方式（50-100字，必须包含与主题相关的具体知识点或操作细节）",
            "host_guide": "主持人引导语（20-50字，自然口语化，结合该环节的实际内容）",
            "interaction": "互动方式（如问答、小组讨论、实践操作等）"
        }}
    ],
    "activity_materials": [
        {{"name": "物资名称（要贴合主题，不要写笼统的'活动资料'）", "spec": "规格要求", "qty": "建议数量"}}
    ]
}}

核心要求：
1. 你必须深入理解主题"{topic}"的含义、背景和核心概念，基于理解生成内容，而不是套模板
2. 如果你的主题涉及专业知识（如MBTI/心理学/编程/艺术等），环节中必须体现该领域的特有概念和术语
3. activity_purpose 200-300字，要写出这个具体主题的独特价值，不能是万能套话
4. activity_content 5-7个环节，每个环节的 content 必须包含与主题直接相关的具体内容
5. activity_materials 5-8项，每一项都要贴合主题的实际需求
6. host_guide 必须是贴合当前环节的自然口语，不能是万能过渡句
7. 如果你不理解这个主题，尽力基于你所知的解释它，不要虚构专业知识'''


def parse_plan_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.rstrip().endswith("```"):
            content = content[: content.rfind("```")]
    return json.loads(content)


def call_llm_for_plan(topic: str, participants: int, api_key: str, api_url: str, model: str) -> dict:
    import requests
    prompt = build_plan_prompt(topic, participants)
    response = requests.post(
        api_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "你是校园活动策划专家，请严格按照要求的JSON格式输出活动方案。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
        },
        timeout=25,
    )
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return parse_plan_response(content)
