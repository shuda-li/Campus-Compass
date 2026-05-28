
# Campus Compass

&gt; 校园活动智能策划 Agent —— 基于确定性引擎 + LLM 创意增强的智能活动规划系统

## 🎯 项目简介

Campus Compass 是一个专为校园活动设计的智能策划 Agent，帮助学生快速生成完整的活动方案，包括活动主题扩展、时间线规划、教室推荐、预算计算等功能。

**核心设计理念**：确定性引擎驱动工作流，LLM 仅作为创意辅助插件，保证系统的可控性和鲁棒性。

## ✨ 主要特性

- 🤖 **智能主题扩展**：深入理解活动主题，生成独特的活动目的和内容
- 📋 **活动方案生成**：自动生成活动时间线、物资清单、宣传建议
- 🏢 **智能教室推荐**：基于多维度评分算法推荐最佳活动场地
- 🧭 **导航指引**：提供从教学区/宿舍区到教室的详细路线
- 💰 **预算计算**：根据参与人数自动计算活动预算
- 💾 **记忆系统**：L1/L2/L3 三层记忆架构，保存用户偏好和历史对话
- 💬 **对话历史管理**：侧边栏展示所有历史对话，支持快速切换
- 🔍 **智能搜索**：支持按关键词搜索历史对话
- ➕ **新建对话**：一键创建新的对话，独立管理多个活动策划
- 🔌 **MCP 工具集成**：集成 Tavily 搜索工具，提供互联网参考信息
- 🛠️ **代理配置**：支持自定义代理配置，解决网络访问问题
- 📱 **流式输出**：实时展示 AI 响应，提升用户体验
- 🎨 **精美界面**：现代化 Web 界面，支持响应式布局
- 🛡️ **容错机制**：LLM 生成失败时自动使用兜底方案，保证可用性

## 🛠️ 技术栈

- **后端**：Python Flask
- **前端**：原生 HTML/CSS/JS + TailwindCSS
- **数据库**：SQLite
- **LLM 支持**：OpenAI API / DeepSeek API / 千问 API
- **记忆系统**：L1（内存）+ L2（SQLite）+ L3（localStorage）
- **MCP 工具**：Tavily 搜索

## 📁 项目结构

```
campus-compass/
├── agent/              # Agent 核心层
│   ├── harness/        # 安全控制与可观测性
│   ├── mcp/            # MCP 工具集成
│   ├── memory/         # 记忆系统
│   ├── tools/          # 工具注册表
│   ├── agent_loop.py   # Agent 主循环
│   ├── llm_client.py   # LLM 客户端
│   ├── proxy.py        # 代理管理
│   ├── skill_loader.py # 技能加载器
│   └── workflow.py     # 工作流引擎
├── engine/             # 引擎层
│   ├── intent_parser.py    # 意图解析
│   ├── topic_analyzer.py   # 主题分析
│   ├── plan_generator.py   # 方案生成
│   ├── room_scorer.py      # 教室评分
│   └── template_matcher.py # 模板匹配
├── skills/             # 技能库
│   ├── lecture_planning/
│   ├── competition_planning/
│   ├── sports_planning/
│   └── ...
├── web/                # Web 展示层
│   ├── app.py          # Flask 应用
│   └── templates/      # HTML 模板
├── tools/              # 工具层
│   ├── db_service.py   # 数据库服务
│   ├── navigation.py   # 导航生成
│   └── budget_calc.py  # 预算计算
├── data/               # 数据层
│   ├── rooms.db        # 教室数据库
│   ├── templates.json  # 活动模板
│   └── init_db.py      # 数据库初始化
├── docs/               # 文档
├── tests/              # 测试
├── config.py           # 配置文件
├── requirements.txt    # 依赖
└── .env.example        # 环境变量模板
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/shuda-li/Campus-Compass.git
cd Campus-Compass/campus-compass
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# DeepSeek 配置（推荐，性价比高）
LLM_API_KEY=sk-your-deepseek-key-here
LLM_API_URL=https://api.deepseek.com/v1/chat/completions
LLM_MODEL=deepseek-v4-flash

# Tavily 搜索 API Key（可选）
TAVILY_API_KEY=tvly-your-tavily-key-here
```

### 4. 初始化数据库

```bash
cd data
python init_db.py
```

### 5. 启动应用

```bash
cd ../web
python app.py
```

然后在浏览器中打开：`http://localhost:5000`

## 💡 使用说明

### 基本流程

1. **输入活动主题**：在输入框中输入你想举办的活动主题，例如 "MBTI 性格探索活动"
2. **确认活动信息**：系统会扩展主题并询问参与人数
3. **生成方案**：点击"生成完整方案"按钮或输入"生成完整方案"
4. **查看结果**：系统会生成完整的活动方案，包括：
   - 活动目的（200-300字，独特内容）
   - 活动时间线
   - 物资清单
   - 教室推荐
   - 导航指引
   - 预算计算

### 侧边栏功能

点击左上角的 ☰ 菜单图标打开侧边栏，可以：

1. **新建对话**：点击「新建对话」按钮创建新的活动策划
2. **查看历史对话**：在列表中查看所有历史对话，按时间倒序排列
3. **搜索对话**：在搜索框中输入关键词，快速找到相关对话
4. **删除对话**：点击对话卡片右侧的垃圾桶图标删除不需要的对话
5. **切换对话**：点击任意对话卡片，快速切换到该对话继续编辑

### 代理配置

如果需要使用代理访问 API：

1. 点击右上角的 ⚙️ 图标展开代理配置面板
2. 开启"使用代理"开关
3. 输入代理地址（例如 `http://127.0.0.1:7897`）
4. 点击"验证"按钮测试连接
5. 配置会自动保存到本地存储

## 📚 设计原理

详见 [docs/设计原理.md](docs/设计原理.md)

## 👥 团队分工

详见 [docs/团队分工文档.md](docs/团队分工文档.md)

## 🔧 开发说明

### 运行测试

```bash
python -m pytest tests/
```

### 项目架构

Campus Compass 采用 4 层架构：

1. **Web 展示层**：用户交互、结果渲染
2. **引擎层**：工作流控制、核心决策
3. **工具层**：纯数据计算
4. **数据层**：持久化存储

### 添加新的活动类型

在 `skills/` 目录下创建新的技能目录，包含 `SKILL.md` 文件即可。

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**Campus Compass** —— 让校园活动策划更简单！🎪

