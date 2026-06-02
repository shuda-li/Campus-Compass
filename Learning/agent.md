这份文档将**脱离视频的时间线**，基于 UP 主“马克的技术工作坊”讲授的逻辑，系统性地为你**重构、深化和拓展**关于 AI Agent 的知识体系。我们将从**底层逻辑 → 核心模式 → 工程实现 → 避坑指南**四个维度进行全面展开。

&#x20;

***

# 第一部分：Agent 的本质 —— 为什么我们需要它？

## 1. 大模型的“缸中之脑”困境

视频开篇指出，单纯的大模型（LLM）本质上是**“互联网文本的压缩包”**。

- **静态性**：训练截止后，知识不再更新。
- **封闭性**：无法直接访问你的私人文件、数据库或实时互联网。
- **无能动性**：它只能“说”，不能“做”。

> **比喻**：LLM 是一个拥有超级大脑的囚犯，它被关在名为“数据”的监狱里，虽然能回答任何理论问题，但无法伸手帮你关掉现实世界里的灯。

## 2. Agent 的定义：赋予大脑手脚

**Agent = LLM（大脑） + Tools（手脚） + Memory（记忆） + Planning（规划）**

视频中强调的核心公式是：

> **Agent = 能感知环境 → 做决策 → 执行动作 → 接收反馈 → 再决策 的闭环系统**

- **感知（Perception）**：通过工具（Tools）获取外界信息（读文件、查API）。
- **决策（Decision）**：LLM 根据当前状态和目标，决定下一步做什么。
- **执行（Action）**：调用工具改变环境（写代码、删文件、发邮件）。

***

# 第二部分：核心运行模式详解

视频重点讲解了两种工业界最常用的模式：**ReAct**​ 和 **Plan-and-Execute**。

## 模式一：ReAct（Reasoning + Acting）—— 边想边做

这是目前 **Cursor、Claude Code、AutoGPT**​ 等工具的主流底层逻辑。

### 1. 核心机制

ReAct 模仿人类解决问题的直觉方式：**思考一步，走一步**。

```
用户任务
  ↓
[Thought] 我需要先看目录结构
  ↓
[Action] 调用 list_files()
  ↓
[Observation] 返回 ["main.py", "utils.py"]
  ↓
[Thought] 发现 main.py 有问题，需要读取
  ↓
[Action] 调用 read_file("main.py")
  ↓
...循环...
  ↓
[Final Answer] 任务完成
```

### 2. 为什么 ReAct 有效？

- **减少幻觉**：强制模型在行动前陈述理由（Thought），降低了瞎编的概率。
- **容错性高**：如果第一步错了，第二步可以根据 Observation 调整策略。

### 3. 工程实现的关键：System Prompt（系统提示词）

视频中用大量篇幅演示：**ReAct 不是训练出来的，是“骗”出来的**。

- 你不需要微调模型，只需要在 System Prompt 里规定**严格的输出格式**。
- 例如强制模型使用 XML 标签：`<thought>`、`<action>`、`<observation>`、`<final_answer>`。
- **模型只是演员，Prompt 才是剧本**。只要剧本写得严丝合缝，模型就会乖乖按 ReAct 流程走。

***

## 模式二：Plan-and-Execute —— 先规划再执行

这是 **Manus、早期 AutoGen**​ 以及复杂企业级 Agent 常用的模式。

### 1. 核心机制

这种模式引入了**分层代理（Agent Hierarchy）**，更像项目经理管员工。

```
用户任务
  ↓
[Planner Agent] 生成计划：
    Step 1: 查今年是哪一年
    Step 2: 查今年澳网男单冠军
    Step 3: 查冠军的家乡
  ↓
[Executor Agent] 执行 Step 1 (ReAct模式)
  ↓
[Replan] 根据实际结果调整后续步骤
  ↓
[Executor Agent] 执行 Step 2
  ↓
...循环...
  ↓
[Final Answer]
```

### 2. 视频中强调的独特设计：Dynamic Replanning（动态重规划）

很多教程只讲“先列清单再干活”，但这份视频特别指出了**关键点**：

> **计划不是一成不变的。**

- 执行完 Step 1 后，必须把“当前年份是 2025”这个事实反馈给 Planner。
- Planner 会生成 **Step 2 的精确版**（“查 2025 年澳网冠军”），而不是最初的模糊版。
- 这解决了“计划基于错误信息导致全盘皆输”的问题。

### 3. 两种模式对比

维度

ReAct

Plan-and-Execute

**适用场景**​

探索性强、路径不确定的任务（Debug、写代码）

步骤清晰、长链条任务（调研、报告生成）

**Token 消耗**​

较高（每步都要带历史）

前期集中，后期较低

**稳定性**​

容易陷入死循环（一直调同一个工具）

全局观强，不容易跑偏

**复杂度**​

结构简单，易实现

结构复杂，需要协调 Planner 和 Executor

***

# 第三部分：从零构建一个 Coding Agent（代码级解析）

视频中最硬核的部分是**手搓一个简化版 Claude Code**。以下是其架构的详细拆解。

## 1. 工具层（Tools）：Agent 的双手

Agent 的能力上限取决于工具有多少。视频实现了三个核心工具：

- **`read_file`**：读取文件内容（感知环境）。
- **`write_file`**：写入/修改文件（改变环境）。
- **`execute_command`**：运行 Shell 命令（高风险，需谨慎）。

> **重要安全设计**：视频中特意提到，对于 `execute_command`，Agent 不能直接执行，必须**询问用户确认**。这是生产级 Agent 的必备安全兜底。

## 2. 核心循环（The Loop）：Agent 的心脏

这是所有 Agent 的灵魂代码逻辑（Python 伪代码）：

```
def run_agent(user_task):
    messages = [SYSTEM_PROMPT, user_task]
    
    while True:
        # 1. 让 LLM 思考
        response = llm.chat(messages)
        
        # 2. 解析 LLM 的输出
        if contains_final_answer(response):
            print("任务完成:", extract_answer(response))
            break
        
        # 3. 提取 Action（工具名 + 参数）
        tool_name, params = parse_action(response)
        
        # 4. 执行工具（关键：不是 LLM 执行，是代码执行）
        result = tools[tool_name](**params)
        
        # 5. 把结果塞回对话，形成闭环
        messages.append(f"<observation>{result}</observation>")
```

### 🚨 关键认知误区纠正

- **误区**：LLM 调用了工具。
- **真相**：LLM 只是在文本里**请求**调用工具（"我想调用 write\_file"）。真正的读写操作是由你的 Python 后端完成的。LLM 永远触碰不到你的文件系统。

## 3. 系统提示词（System Prompt）的精妙之处

视频展示了 Prompt 必须包含的要素：

1. **角色设定**：你是编程助手。
2. **环境信息**：当前目录结构、操作系统（帮助模型理解上下文）。
3. **工具说明书**：每个工具的入参、出参、功能描述（JSON Schema 风格最佳）。
4. **行为约束**：必须先用 `<thought>`思考，再用 `<action>`调用。

***

# 第四部分：进阶知识与避坑指南（视频隐含知识点拓展）

基于视频内容，我为你补充一些 UP 主没来得及细讲，但在实战中**至关重要**的知识点。

## 1. 上下文窗口（Context Window）危机

ReAct 循环中，每一次 Observation（比如读取一个大文件）都会占用 Token。

- **问题**：几轮下来，对话历史爆满，导致 Agent 失忆或费用爆炸。
- **解决方案**：
  - **截断（Truncation）**：只保留最近的 N 轮对话。
  - **压缩（Compression）**：用另一个 LLM 把历史总结成摘要。
  - **RAG**：不让 Agent 直接读大文件，而是先检索相关片段（Chunking）。

## 2. 工具调用的可靠性（JSON Mode vs XML）

视频中使用的是 XML 标签（`<action>`），但在工业界：

- **XML/字符串匹配**：容易解析失败（模型偶尔漏写标签）。
- **JSON Mode / Function Calling**：OpenAI/Claude 等厂商提供的专用接口，强制模型输出合法 JSON，解析成功率 99% 以上。这是构建稳定 Agent 的首选。

## 3. 退出机制（Exit Strategy）

视频中提到 `Final Answer`。

- **风险**：Agent 可能永远不输出 Final Answer，陷入死循环。
- **工程手段**：必须设置 `max_steps`（最大步数限制，如 15 步），超过即强制终止。

## 4. MCP（Model Context Protocol）

视频开头提到了“与我之前发的 MCP 终极指南有所重合”。

- **MCP**​ 是 Anthropic 提出的标准协议，目的是解决 **“工具碎片化”**​ 问题。
- 以前：Agent A 写了读取文件的工具，Agent B 也要重写一遍。
- 有了 MCP：工具变成标准化服务，任何支持 MCP 的 Agent 都能直接调用。

***

# 总结：一句话看懂 Agent

> **Agent 并不是一个更聪明的模型，而是一个“通过 Prompt 逼迫模型按特定格式说话，再由代码监听这些话并代为执行操作的自动化脚本。”**

当你理解了这一点，你会发现：

- **Cursor**​ = LLM + 代码索引工具 + Diff 预览 UI
- **Manus**​ = LLM + 浏览器控制工具 + 报告生成工具
- **Claude Code**​ = LLM + 文件系统工具 + Git 集成

它们的核心代码，都逃不出视频里演示的那个 **While 循环**。
