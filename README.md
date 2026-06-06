# Campus Compass · 校园活动智能策划 Agent

> ✦ DeepSeek 驱动 ✦ Plan-Aware 关键词锚定 ✦ 一键导出 Word

Campus Compass 是一个 LLM 驱动的校园活动策划 Agent，基于 **Agent / Skill / Harness 三层架构**，通过流式对话生成完整的活动方案——包含活动目的、环节设计、物资清单、教室推荐和预算计算。

---

## 界面预览

UI：玻璃拟态面板、深空背景、星云紫 + 琥珀金配色、聚焦白光环。

---

## 核心特性

### Agent 智能体
- **ReAct 循环**：Thought → Action → Observation 闭环，LLM 自主选择工具调用顺序
- **Circuit Breaker**：检测连续重复工具调用，防止死循环
- **Sub-Agent 隔离**：classroom_scout / budget_analyst 子代理，独立上下文 + 工具白名单
- **TodoWrite 动态规划**：Agent 自主拆解复杂任务、跟踪进度

### 修改意图检测（Plan-Aware 关键词锚定）
- **关键词锚定**：从生成的 Plan 构建倒排索引，用户反馈反向匹配（精确→子串→模糊），精准定位修改目标
- **通用意图检测**：覆盖时间/场地/人数/内容/预算 5 种修改类型
- **硬约束 vs 软偏好**：分句检测，"必须"→硬约束 ⚠️ / "最好"→软偏好 💡
- **学习机制**：Token 集合 Jaccard 相似度匹配，LLM 成功提取后自动沉淀为可复用模式

### 技能系统
- **6 种活动类型**：讲座、竞赛、演出、展览、实践、运动
- **88+ 体育关键词** + **50+ 电竞关键词**，精准命中
- **LLM 语义兜底**：冷门关键词自动调用 LLM 分类
- **场地智能路由**：电竞→机房区(E506/E507)，体育→体育区(体育馆/田径场)，其他→E教学楼

### 教室推荐
- **双维度评分**：填充率 50%（最优 70-80%）+ 拓扑距离加权 50%
- **21 间真实教室**：E 座 1F，含阶梯教室、普通教室、模拟法庭、录播教室
- **拓扑距离**：基于校园地图的 Dijkstra BFS 最短路径

### UI / UX
- **Star Rail 星穹铁道美学**：玻璃拟态、渐变金字、星座 SVG 装饰、六边形元素
- **白天/黑夜模式**："曙光"浅紫暖金 / "星夜"深空紫
- **自定义背景图片**：75% 透明度叠加
- **创意度滑块**：0.3~1.2 可调温度
- **聚焦白光环**：输入框聚焦白辉光晕
- **一键导出 Word**：完整方案导出为 .docx，保持 Star Rail 配色

### 记忆系统
- **L1**：会话内存（dict）
- **L2**：SQLite 持久化（history.db）
- **L3**：长期偏好（.memory/ JSON）
- **换题检测**：异类关键词 + 直接换题短语 + 锚定优先判定

---

## 技术栈

| 层 | 技术 |
|------|------|
| 后端 | Python 3.12 + Flask |
| 前端 | 原生 HTML/CSS/JS + TailwindCSS CDN + Font Awesome 4 |
| AI | DeepSeek API (deepseek-chat) |
| 数据库 | SQLite |
| 文档导出 | python-docx |
| 记忆 | L1(dict) + L2(SQLite) + L3(JSON) |

---

## 项目结构

```
campus-compass/
├── agent/                   # Agent 核心层
│   ├── agent_loop.py        #   ReAct 主循环 + Circuit Breaker + Scratch 缓存
│   ├── state.py             #   AgentState 数据类
│   ├── llm.py               #   LLM 流式/非流式调用
│   ├── llm_client.py        #   LLM 客户端（旧版兼容）
│   ├── formatter.py         #   方案 HTML 格式化
│   ├── skill_loader.py      #   技能匹配（关键词+LLM兜底）
│   ├── proxy.py             #   代理管理
│   ├── word_export.py       #   Word 文档导出
│   ├── workflow.py          #   旧版流水线（已弃用）
│   ├── harness/             #   驾驭层
│   │   └── observ.py        #     结构化 Trace
│   ├── mcp/                 #   MCP 工具
│   │   └── tavily_search.py #     LLM 搜索（替代 Tavily API）
│   ├── memory/              #   记忆系统
│   │   ├── session.py       #     L1+L2 记忆
│   │   ├── persistence.py   #     L3 长期记忆
│   │   └── trim.py          #     Token 预算管理
│   └── tools/               #   工具注册
│       ├── registry.py      #     工具白名单 + 调度 + 截断
│       └── subagent.py      #     LLM 驱动子代理
├── engine/                  # 引擎层
│   ├── plan_generator.py    #   方案生成 prompt + JSON 解析（3层兜底）
│   ├── plan_anchor.py       #   Plan-Aware 关键词锚定（倒排索引+反向匹配）
│   ├── intent_detector.py   #   通用修改意图检测（5类型×3层漏斗）
│   ├── time_intent.py       #   时间变更检测（15关键词+9正则+学习）
│   ├── intent_parser.py     #   意图解析
│   ├── topic_analyzer.py    #   主题复杂度分析
│   ├── completeness_checker.py  # 信息补全追问（最多3次）
│   ├── room_scorer.py       #   教室评分
│   ├── room_selector.py     #   双维度教室选择
│   └── template_matcher.py  #   模板匹配
├── skills/                  # 技能库
│   ├── lecture_planning/    #   讲座策划
│   ├── competition_planning/#   竞赛策划
│   ├── performance_planning/#   演出策划
│   ├── exhibition_planning/ #   展览策划
│   ├── practice_planning/   #   实践策划
│   └── sports_planning/     #   运动+电竞策划
├── web/                     # Web 层
│   ├── app.py               #   Flask 应用（路由+会话管理+SSE流式）
│   └── templates/
│       └── index.html       #   Star Rail 主题单页应用
├── tools/                   # 工具层
│   ├── db_service.py        #   教室数据库查询
│   ├── budget_calc.py       #   预算计算
│   └── topo_loader.py       #   拓扑距离加载器
├── data/                    # 数据层
│   ├── init_db.py           #   数据库初始化（21教室+4场馆）
│   ├── map.json             #   校园拓扑地图
│   └── templates.json       #   活动模板
├── docs/                    # 文档
│   ├── 开发日志.md           #   完整开发记录
│   ├── 设计原理.md           #   架构设计
│   ├── 改进方向.md           #   未来改进清单
│   └── 教室评分算法分析.md    #   评分算法详解
├── Learning/                # 学习材料
├── tests/                   # 测试
├── config.py                # 配置文件
├── run.py                   # 一键启动脚本
├── requirements.txt         # 依赖清单
├── .env.example             # 环境变量模板
└── README.md
```

---

## 快速开始

### 一条命令启动

```bash
python run.py
```

自动完成：依赖检查 → 安装缺失 → 启动 Flask → 打开浏览器。

### 或手动启动

```bash
pip install -r requirements.txt
cp .env.example .env    # 编辑 .env 填入 DeepSeek API Key
python web/app.py
```

浏览器打开 `http://localhost:5000`

### 环境变量

```env
# DeepSeek API（必需）
LLM_API_KEY=sk-your-deepseek-key-here
LLM_API_URL=https://api.deepseek.com/v1/chat/completions
LLM_MODEL=deepseek-chat
```

OpenAI 兼容的 API 也可用，修改 `LLM_API_URL` 和 `LLM_MODEL` 即可。

---

## 使用流程

1. **输入主题** → 输入活动主题（如"50人的Python编程竞赛"）
2. **确认人数** → Agent 自动扩展简略主题，询问参与人数
3. **补充信息** → 可选补充时间、物资、人员等（最多追问 3 次）
4. **生成方案** → 点击"生成完整方案"，实时流式输出
5. **迭代改进** → 方案生成后输入改进需求：
   - "把主办单位改成电竞社" → 关键词锚定到 organizer 字段
   - "开幕致辞改短一点" → 锚定到 activity_content[0].phase
   - "投影仪多加 2 台" → 锚定到 activity_materials[0].name
6. **导出 Word** → 点击"一键导出完整方案"下载 .docx

---

## 设计原理

### Agent / Skill / Harness 三层架构

| 层 | 职责 | 对应模块 |
|------|------|------|
| **Agent** | 决策引擎，ReAct 循环，工具选择 | `agent_loop.py` |
| **Skill** | 领域知识，SOP 模板，约束规则 | `skills/*/SKILL.md` |
| **Harness** | 安全护栏，Token 预算，Trace，白名单 | `harness/` + `tools/registry.py` + `memory/` |

### 缓存优先上下文架构

参考 DeepSeek-Reasonix 的四支柱模型：
- **不可变前缀**：System Prompt + 第一条用户输入（永不修改，前缀缓存 100% 命中）
- **追加日志**：LLM 回复 + 工具返回（只追加不删除）
- **易变暂存**：系统干预统一收集为单条消息追加

### Plan-Aware 关键词锚定

```
Plan: {organizer: "计算机学院", activity_content: [{phase: "开幕致辞"}, ...]}
       ↓ build_plan_index()
Index: {"计算机学院"→organizer, "开幕致辞"→activity_content[0].phase, 
        "主办单位"→organizer (别名), ...}
       ↓
User: "把主办单位改成电竞社"
       ↓ anchor_feedback()
"主办单位" → organizer 字段 (exact, 1.0)
       ↓ format_anchor_hint()
prompt += "📍 organizer「主办单位」→ 用户要求修改此字段"
```

---

## 开发日志

完整开发记录见 [docs/开发日志.md](docs/开发日志.md)，包含所有 P0/P1/P2 修复、架构演进和设计决策。

---

## License

MIT

---

**Campus Compass** — 让校园活动策划更简单 ✦
