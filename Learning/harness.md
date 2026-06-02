# Harness Engineering：把"聪明大脑"变成"可投产系统"的全套工程学

> 注：以下内容以该视频（BV1Zk9FBwELs，「code的秘密花园」出品）的论述框架为主干，融合 Anthropic / OpenAI 公开发表的工程博客与基准实验数据，**从架构层面**把 Harness 拆透。

***

## 0. 先讲清楚：Harness 不是什么

常见误解

纠正

"Harness 是更高级的 Prompt Engineering"

❌ Prompt 只是 Harness 内部最微小的一个零件

"Harness 是某个框架（LangGraph / CrewAI / AutoGen）的新名字"

❌ 它是**横跨所有框架**的元层——你用任何框架都逃不开它

"Harness = 工具调用 (Tool Use)"

❌ 工具调用只是执行层的子集，Harness 还包括记忆、安全、编排、观测、恢复……

"换个更强的模型就能替代 Harness"

❌ **同一模型，仅换 Harness，CORE-Bench 成绩 42% → 78%**（Claude Opus 4.5 + Smolagents vs + Claude Code harness）

**一句话精确定义**：

> **Harness = 大模型 / Agent 之外，所有让它在真实世界里"持续、可控、可审计、可恢复地干活"的工程基础设施的总和。**

业内那句口号不是修辞——是架构事实：

```
Agent=Model+Harness
```

模型负责**推理**（think），Harness 负责**一切 else**。

***

## 1. 为什么 Harness 现在成了核心问题（而不在 2023 年）

### 1.1 AI 工程化的三阶段演进（视频核心脉络）

```
2023  Phase 1：Prompt Engineering（提示词工程）
       ───────────────────────────────────────
       问题域：怎么把话说清楚？
       手法：  角色设定、Few-shot、CoT、输出格式约束
       局限：  一次性的输入输出。模型"说完就忘"，碰不到真实环境

2024  Phase 2：Context Engineering（上下文工程）
       ────────────────────────────────────────
       问题域：怎么在对的时候把对的信息喂给模型？
       手法：  RAG、记忆系统、对话历史管理、摘要压缩、
               project rules 文件（CLAUDE.md / agents.md / .cursorrules）
       局限：  有了"信息环境"，但模型仍然缺乏执行闭环和治理

2025─  Phase 3：Harness Engineering（驾驭工程 / 马具工程）
       ────────────────────────────────────────
       问题域：怎么让 AI 不只"能做事"，而是"稳定、安全、可审计地
               把一件复杂的事从头干到尾"？
       手法：  工具供给 + 任务编排 + 安全边界 + 检查/反馈闭环
               + 状态持久化 + 观测性 + 错误恢复 + 人工审批门禁
```

三者是**嵌套关系**，不是替代关系：

```
┌─────────────────────────────────────────────┐
│                 Harness Engineering           │  ← 管"全程靠谱"
│  ┌─────────────────────────────────────────┐ │
│  │        Context Engineering               │ │  ← 管"信息对不对"
│  │  ┌───────────────────────────┐           │ │
│  │  │  Prompt Engineering       │           │ │  ← 管"听得懂话"
│  │  │  (角色/CoT/格式/示例)     │           │ │
│  │  └───────────────────────────┘           │ │
│  │  + RAG + Memory + 规则文件 + 压缩策略      │ │
│  └─────────────────────────────────────────┘ │
│  + Tools + Orchestration + Safety + Ops        │
└─────────────────────────────────────────────┘
```

### 1.2 那个关键转折：模型能力曲线 vs 落地瓶颈曲线

到 2025 年末，行业集体撞上一堵墙：

- 模型越来越强（GPT-4o → Claude 3.5/4.x → Gemini 2.x），**智力上限不是瓶颈**
- 但 Agent 跑长任务时：上下文溢出 → 忘了前面定的规范 → 工具误调用 → 无法恢复 → 产出不可信

Anthropic 在 long-running agents 的讨论中明确指出：**agent 做长任务会跨多个上下文窗口，每次新会话像"一个新工程师接班"，没有之前发生过什么的记忆**。

OpenAI 的 Codex 团队给出一个极具冲击力的实证：三人小团队，**全靠 Harness 引导 AI**，产出了上百万行生产代码，产品已在内部上线。

LangChain 的实验更直接：同一模型，**仅改进 Harness 层**（工具格式、编辑接口、执行沙箱），在 Terminal-Bench 2.0 上从第 30+ 名跳到第 5 名。

**结论不是"Prompt 不重要"，而是：在模型无代差的区间里，Harness 的投资回报率远高于换模型或雕 prompt。**

***

## 2. Harness 的分层架构：它内部到底长什么样

这是视频最有价值的部分——把 Harness 从口号拆成**可实现的软件层次**。综合视频论述与业界实践，一个生产级 Harness 至少分 **三层（也可展开为六层）**：

### L0 · 模型层（不属于 Harness，但是一切的锚点）

```
Model (LLM)
  │  能力边界：推理、生成、Function/tool-call 协议
  │  不拥有的东西：手脚、记忆、时钟、文件、网络、价值观、自我检查能力
  └──  Harness 的所有层，都是为这个"只有嘴的大脑"补上的器官
```

### L1 · 执行层（Execution Layer）—— Agent 的「手、脚、感官」

这是最接近大家对 Agent 的直觉认知：**工具调用**。

组件

作用

硬核要点

**Tool Registry**​

声明可用工具清单（schema、描述、参数校验）

工具**不是越多越好**——给只读 Agent 开放 `rm -rf`等价于给幼儿上膛的枪

**Sandbox / Runtime**​

隔离执行环境（Docker、seccomp、资源配额）

生产级必须：namespace 隔离、超时、内存上限、IO 限额

**File Ops**​

read / write / patch（最好是基于 diff 而非全量覆写）

关键设计：写操作应走 `patch`语义，保留原文件可 rollback

**Shell / Process**​

执行命令

必须设允许列表（allowlist）+ 危险命令拦截 + human-in-the-loop 确认

**Browser / DOM**​

网页交互

截图 + accessibility tree 双通道；注意 token cost

**MCP Server（Model Context Protocol）**​

标准化工具接入协议（Anthropic 提出）

让工具变成"即插即用"的服务，而非每个 Agent 硬编码一套

> **架构原则**：执行层应当实现 **最小权限原则（Least Privilege）**——每个 Agent 角色的 toolset 应按需裁剪，不是一股脑全挂上去。

### L2 · 环境与状态层（Environment & State Layer）—— Agent 的「小脑 / 工作记忆」

模型的天生缺陷：**无状态、无持久记忆、注意力是稀缺资源**。

组件

作用

实现思路

**Working Memory**​

当前任务的对话历史、最近 observation

环形缓冲 / 滑动窗口；到 \~80% 容量时触发压缩

**Persistent State**​

跨会话存活的信息：项目进度、决策日志、错误册

SQLite / JSONL / vector DB；结构化 > 非结构化

**Context Architecture（上下文架构）**​

规则文件的组织方式

**不要一个 3000 行 CLAUDE.md**——OpenAI 团队踩过这个坑：超大规则文件 → 模型忽略关键信息。正确做法：`CLAUDE.md`只写 \~100 行索引，详细内容拆到 `docs/frontend.md`、`docs/security.md`等，按需读取（on-demand load）

**Knowledge / Skills**​

可复用的工作流封装（agent skills）

类似"技能包"：一套 prompt template + tool subset + 验收条件

**上下文溢出的核心解法不是"更大的窗口"（那是军备竞赛），而是信息蒸馏（distillation）**：

```
当 context 占用 ≥ 80%：
  1. Agent 生成一份交接摘要（做了什么、决策了什么、当前状态、open issues）
  2. 摘要存入 Persistent State
  3. 开启新上下文，只注入摘要 + 必要索引
  → 类似 OS 的 swap / checkpoint-restart
```

### L3 · 治理与编排层（Governance & Orchestration Layer）—— Harness 的「方向盘 + 仪表盘 + 刹车」

**这一层是区分"玩具 Agent"与"生产 Agent"的分水岭**，也是视频里最硬核的部分。

#### ① 任务编排（Orchestration）

模式

机制

适用

**Linear Pipeline**​

固定步骤串执行

确定性流程（CI/CD-style）

**ReAct Loop**（边想边做）

Thought→Action→Observation 循环

探索性、调试、动态路径

**Plan-then-Execute**（先规划后派工）

Planner 生成 DAG / step list → Executor 依次执行 → 失败触发 REPLAN

多步骤长任务、可分解工作

**Multi-Agent / Sub-Agent**​

主 Agent 派分子任务给 specialist agents，并行汇合

互不依赖的工作包

视频中提到的关键设计：**不是让一个全能 Agent 从头滚到尾**，而是承认上下文有限，用"接力"机制——子 Agent 做完一个 chunk → 交摘要 → 下一个接手。

#### ② 规则 / 护栏系统（Rules & Guardrails）

视频里提到的 `rules`、`hooks`分别对应弹性约束与硬约束：

```
Rules（软性护栏 / "道德准则"）
  ───────────────────────────
  · 行为优先级（例如：正确性 > 可读性 > 速度）
  · 代码风格、提交规范、安全偏好
  · 价值观/约束（不拍马屁、不瞎猜用户意图 → 反问）
  → 实现方式：写进 system prompt / CLAUDE.md / rules.d 目录

Hooks（硬性拦截 / "警察"）
  ───────────────────────────
  · 禁止 delete without confirm
  · 禁止 commit 到 main 无 review
  · 敏感词 / 密钥泄露扫描（pre-commit hook 语义）
  → 实现方式：在 tool dispatch 层做拦截（code path 级别，不可绕过）
```

#### ③ 反馈闭环与自检（Feedback Loop）

这是 Harness 里**最反直觉但最能提升成功率**的组件：

```
Agent writes code
  → Harness 自动触发 lint (ruff/eslint)
  → Harness 自动触发 type check (mypy/tsc)
  → Harness 自动 trigger 测试 suite (pytest/vitest)
  → 若 fail → 把 error output 塞回 Agent 的 observation
              → Agent 读 error → 修订 → retry（带 max_retries）
  → 若 pass → 标记 done，写日志
```

Mitchell Hashimoto（HashiCorp 联合创始人）的表述极为精准：

> **"Whenever AI makes the same mistake twice, engineer a solution so it never happens again."**
>
> （每当 AI 犯同一种错误两次，就工程化一个方案，让它永远别再犯。）

这就是 Harness 的哲学内核——**不是训模型，而是建系统**：把错误模式沉淀为 rule / hook / test / skill，让系统随运行逐步变聪明。

#### ④ 可观测性与日志（Observability）

```
每次 step 至少记录：
  · timestamp | step_id | agent_role
  · thought（文本）
  · action（tool_name + args）
  · observation（截断版，避免爆 log）
  · token_usage / cost
  · status: success | error | blocked_by_policy
```

没有日志的 Agent 是黑盒——出了问题你连"它在哪一步疯的"都不知道。

#### ⑤ 恢复与兜底（Recovery）

故障

Harness 的恢复策略

模型 API 超时

指数退避重试（带 jitter）

工具执行崩溃

捕获异常 → 返回 observation 为 error msg → Agent 自行调整

上下文溢出

checkpoint → 蒸馏摘要 → 新 session 重启

Agent 死循环（同一 action 重复 N 次）

circuit breaker：强制中断 → human review

产出违反安全策略

block + 上报 + 回滚

***

## 3. 那个经典比喻的"工程翻译"

视频和所有衍生文章都用**马具/缰绳**比喻，我们把这个比喻精确地映射到代码架构：

马具部件

Harness 里的工程对应

为什么对应

**缰绳（Reins）**​

Guardrails / Rules / Hooks / Policy Engine

控制"能不能往某方向走"——拦截越权、拦截危险操作

**马鞍（Saddle）**​

Execution Environment + State Management

提供稳定"承载面"——沙箱、工作目录、状态挂载点

**马镫（Stirrups）**​

Tool Registry + MCP + Skills 库

让骑手上马、发力——标准化的工具接入面

**衔铁/口衔（Bit）**​

Prompt 约束 + 输出 schema 强制（JSON mode / grammar constrained generation）

控制"嘴怎么张、怎么说"——模型不得自由格式

**蹄铁（Shoes）**​

沙箱隔离 + 资源 quota

防它跑碎系统

**骑手（Rider）**​

Human-in-the-loop 审批门禁 + 你写的规则

**最终控制权永远在人类定义的 policy 上**​

一句话：**模型是发动机，Harness 是底盘 + 方向盘 + 刹车 + 仪表盘 + 车道线**。

***

## 4. 关键设计原则（视频隐含但必须明说的部分）

### 原则 1：「与模型的运行原理自洽」——别跟 Transformer 对着干

视频中提到一条金标准：**不要随意篡改历史对话或 system prompt**。

深层原因：LLM 推理依赖 **KV Cache**。如果你在 loop 中间动态改写历史（比如偷偷删掉某些 message 再塞新内容），缓存失效 → 整段重新 compute → token 浪费 + 延迟飙升 + 可能行为漂移。

正确做法：

- 用 **append-only**​ 的 message list 做主历史
- 需要"遗忘"时，用摘要替换（checkpoint 机制），而非就地编辑
- 需要注入新信息：用 tool observation 或专门的 `system_event`message 类型，而非改写旧 assistant content

### 原则 2：工具不是越多越好（决策疲劳是真实存在的）

给 Agent 挂 50 个工具，每个 step 的 tool-choice 变成一个 50-way softmax —— 不仅**选错概率上升**，而且 prompt 里工具描述占掉的 token 也在挤掉真正有用的上下文。

最佳实践：

- 每个 Agent **角色**配一个 **最小 toolset**
- 通用能力走 **MCP**​ 按需挂载
- 用 `agent-skills`模式封装"复合技能包"（例如 `skill:run-tests`、`skill:create-pr`），降低每步决策复杂度

### 原则 3：事故凝结为规则（Error → Rule → Hook 链路）

这才是 Harness 的工程化精髓，也是它区别于"prompt 调优"的地方：

```
AI 犯错（例：把 API key 写进了代码）
                     │
                     ▼
          记入 error_log / pattern_db
                     │
            反复出现？→ 提炼成 rule："禁止硬编码 secret"
                     │
                     ├──→ 软规则：写进 CLAUDE.md / rules.d/secrets.md
                     │     （下次 prompt 里提醒它）
                     │
                     └──→ 硬拦截：写进 hooks/pre-commit
                           （runtime 层直接 block，不经过 LLM 裁决）
```

**Harness 是自我强化系统：跑得越久 → 积累的 guardrails 越多 → 越不容易翻车。**

### 原则 4：模型无关性（Orthogonality）

你的 Harness **不应**跟某个模型的怪癖深度耦合（比如针对 Claude 的特定 XML tag 格式硬编码解析器）。正确抽象：

```
Harness Core（模型无关）
  ├── Adapter: ClaudeAdapter    ← 把 Claude 的 tool_call 格式归一化
  ├── Adapter: OpenAIAdapter     ← 把 OpenAI 的 function_call 格式归一化
  ├── Adapter: GeminiAdapter
  └── 上层逻辑（orchestrator / state / rules / sandbox）完全不关心底层是哪个模型
```

这样明天换模型，Harness 不变——**模型是耗材，Harness 是资产**。

***

## 5. 一个最小但完整的 Harness 伪代码结构

把上面所有层收束成一个你能直接对照实现的骨架：

```
class Harness:
    def __init__(self, model, tools, rules, sandbox):
        self.model   = model              # L0 接口
        self.tools   = ToolRegistry(tools) # L1 执行层
        self.rules   = RulesEngine(rules)  # L3 护栏
        self.state   = StateStore()         # L2 持久状态
        self.sandbox = sandbox              # L1 沙箱
        self.logger  = Observability()      # L3 观测
        self.max_steps = 25

    def run(self, task: str):
        msgs = [
            system_msg(self.rules.system_prompt()),
            user_msg(task),
        ]

        for step in range(self.max_steps):
            # ── 上下文健康检查 ──────────────────────────
            if self._context_needs_compaction(msgs):
                msgs = self._compact(msgs)

            # ── 让模型思考 ──────────────────────────────
            resp = self.model.chat(msgs, tools=self.tools.schema())
            self.logger.log_step(step, resp)

            # ── 意图解析 ────────────────────────────────
            if resp.is_final_answer():
                return resp.text()

            act = resp.tool_call()  # {name, args}

            # ── ★ 硬拦截（Hooks 层）──────────────────────
            veto = self.rules.pre_tool_call_veto(act)
            if veto:
                obs = f"[BLOCKED by policy] {veto.reason}"
            else:
                # ── 执行（沙箱内）────────────────────────
                obs = self.sandbox.execute(
                    lambda: self.tools.dispatch(act.name, act.args),
                    timeout=30,
                )

            # ── 记录状态 ────────────────────────────────
            self.state.append_event(step, act, obs)

            # ── 把 observation 喂回去 ────────────────────
            msgs.append(tool_result_msg(obs))

        raise TimeoutError("Agent exceeded max_steps — possible loop / stall")
```

**总共不到 60 行逻辑，但已经包含了 L1+L2+L3 的所有关键齿轮**：沙箱、规则拦截、状态持久化、上下文压缩触发、观测日志、步骤上限。

***

## 6. 回到那句判断："模型之外，皆是 Harness"

视频最后（以及衍生讨论）引出的核心洞察是：

维度

模型决定

Harness 决定

推理质量（"聪不聪明"）

★★★★★

★☆（好的 harness 释放而非压制模型能力）

能否接触真实环境

✗ 模型本身做不到

★★★★★

会不会跑偏 / 删库

✗ 模型没概念"危险"

★★★★★（guardrails）

长任务能否跑到终点

△ 靠上下文长度硬撑

★★★★★（state mgmt + recovery）

产出是否可审计

✗

★★★★★（logging + versioning）

团队能否规模复用

△ 每人各写各的 prompt

★★★★★（harness 作为共享基建）

所以 Harness 本质上回答的是一个很老派的工程问题：

> **给定一颗越来越强的"智能芯"，你怎么给它造一台可靠的机器？**

不是 fine-tune 它，不是 prompt 它到完美，而是——**用软件工程的经典手段：隔离、约束、日志、测试、恢复、权限——把概率性的文本生成器，包成一个确定性的任务执行系统。**

***

接着按你上一个问题的 Agent 代码脉络，**把"手写 ReAct Agent"的代码逐层往上叠——加 rules/hooks → 加 memory compaction → 加 sub-agent 编排 → 加 error→rule 自学习**，把它从一个 demo 推到接近真实 Harness 的形态。

承接上文，我们从 **“架构认知”**​ 下沉到 **“工程实现细节”**。这一部分将基于视频中提到的 **Claude Code / Codex / Smolagents**​ 等工业级案例，把 Harness 中那些 **“不说不知道，一说全是坑”**​ 的硬核细节拆解出来。

&#x20;

我们将重点攻克三个最难的工程关卡：**上下文工程的物理极限、工具调用的确定性博弈、以及多 Agent 的分布式编排**。

***

## 1. 上下文工程（Context Engineering）的硬核解法

视频里提到一个关键痛点：**模型记不住事**。这不是模型的智商问题，而是物理限制。Harness 必须解决 **“上下文窗口（Context Window）”**​ 的熵增问题。

### 1.1 上下文的三种形态与生命周期

在成熟的 Harness 中，上下文不是一条无限变长的聊天记录，而是分为三个层级：

层级

名称

存储介质

生命周期

示例内容

**L1**​

**Working Context**​

RAM (KV Cache)

单次 Session

当前正在编辑的文件、最近的 5 轮对话

**L2**​

**Project Context**​

Vector DB / File System

跨 Session

`CLAUDE.md`, `README.md`, 代码索引

**L3**​

**Global Context**​

Database / Logs

永久

用户偏好、历史错误模式、已完成的任务摘要

**Harness 的核心调度逻辑：**

当 L1 满了（例如达到 128k tokens 的 80%），Harness 必须执行 **Compaction（压缩）**。

### 1.2 Compaction 的算法实现

视频里提到“不要让一个文件太大”，这背后是 **Attention Sink（注意力沉没）**​ 问题。模型对开头的记忆会被稀释。

**错误的压缩方式：**

> 直接截断最早的历史消息。❌（丢失关键信息）

**正确的压缩方式（Checkpointing）：**

Harness 必须强制 Agent 在上下文溢出前停下来，执行一个 **“交接仪式”**：

```
def compact_context(harness, messages):
    # 1. 注入一个特殊的 System Instruction
    compaction_prompt = """
    You are a summarizer. Summarize the conversation history into a structured handover document.
    Include:
    1. Original Goal.
    2. What has been done (Files changed, commands run).
    3. Current State (What is half-done).
    4. Next Steps.
    Be concise. This summary will replace the chat history.
    """

    # 2. 让模型生成摘要
    summary = harness.model.chat(compaction_prompt + messages)

    # 3. 重置上下文：只保留 System Prompt + Summary + 最近 N 条关键消息
    new_messages = [
        system_prompt,
        {"role": "system", "content": f"Previous Context Summary:\n{summary}"},
        messages[-3:]  # 保留最近的交互，防止断层
    ]
    return new_messages
```

**这就是为什么视频强调“模型之外皆是 Harness”**：模型不知道自己快没内存了，也不知道什么时候该做总结，**调度和决策必须由 Harness 代码来做**。

***

## 2. 工具调用（Tool Use）的确定性陷阱

视频中演示了 Agent 写贪吃蛇游戏。这里有一个巨大的工程鸿沟：**模型输出的文本是概率性的，而代码执行是确定性的。**

Harness 必须充当 **“适配器（Adapter）”**，解决两者的阻抗不匹配。

### 2.1 工具定义的严格性（Schema Enforcement）

视频里提到用 XML 标签（`<action>`），但在生产环境中，**Function Calling**​ 配合 **JSON Schema**​ 才是正解。

**硬核要求：**

- **无歧义**：参数类型必须是强类型（String, Int, Enum）。
- **无自由发挥**：禁止模型在参数里夹带私货（例如把自然语言描述塞进 int 字段）。

```
# Harness 中的工具注册表示例
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace old_code with new_code in a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "old_code": {"type": "string", "description": "Exact string to find"},
                    "new_code": {"type": "string", "description": "String to replace with"}
                },
                "required": ["path", "old_code", "new_code"]
            }
        }
    }
]
```

### 2.2 编辑工具的原子性问题（The Atomicity Problem）

视频里 Agent 直接写文件。这在真实世界中极其危险，因为模型可能会：

1. 生成不完整的代码。
2. 覆盖掉重要文件。

**工业级 Harness 的解决方案：Patch-Based Editing（基于补丁的编辑）**

不要给 Agent `write_file`（全量覆写）权限，而是给 `apply_patch`。

```
# Harness 内部的 Patch 应用逻辑
def apply_patch(file_path, patch_content):
    """
    Apply a unified diff patch.
    This ensures the Agent only describes changes, not full files.
    """
    try:
        # 1. 备份原文件 (Snapshot)
        backup = read_file(file_path)
        
        # 2. 尝试应用补丁
        subprocess.run(["patch", file_path, patch_content], check=True)
        
        # 3. 验证语法（Guardrail）
        if file_path.endswith(".py"):
            subprocess.run(["ruff", "check", file_path], check=True)
            
        return "Patch applied successfully."
    
    except Exception as e:
        # 4. 回滚 (Rollback)
        write_file(file_path, backup)
        return f"Patch failed: {e}. File restored."
```

**这就是 Harness 的“马镫”**：它限制了模型的能力（不能随便乱写），但反而提升了成功率（不会因为少写一个括号毁掉整个项目）。

***

## 3. 规则系统（Rules & Hooks）的编译原理视角

视频里提到的 `rules`和 `hooks`不仅仅是文本提示词，它们在 Harness 中处于**编译期**和**运行期**的不同位置。

### 3.1 软规则（Soft Rules / Prompts）

位于 **System Prompt**​ 中。

- **性质**：建议性。
- **例子**：“代码注释要友好”、“优先考虑性能”。
- **失效场景**：模型压力大时（上下文快满了）会忽略这些。

### 3.2 硬钩子（Hard Hooks / Guards）

位于 **Tool Dispatch Layer（工具分发层）**。

- **性质**：强制性，代码级拦截。
- **例子**：禁止删除根目录、禁止访问 `/etc/passwd`。

**Harness 的执行流必须包含 Hook 检查：**

```
Agent Output (Text)
      │
      ▼
[Parser] 解析出 Tool Call
      │
      ▼
[Pre-Hook]  ──── 检查权限 ────▶ 拦截 (Block) ──▶ 返回 Error Observation
      │                                       
      ▼ (Pass)
[Executor] 执行工具
      │
      ▼
[Post-Hook] ──── 检查输出 ────▶ 记录日志 / 触发警报
      │
      ▼
返回 Observation 给 Agent
```

**视频中提到的“Mitchell Hashimoto 原则”**​ 在这里体现为：一旦 Post-Hook 发现模型犯了某个错误（比如把 Secret 打印到了日志），Harness 必须立即更新 **Rule Set**，把这个禁忌写入 `CLAUDE.md`或 Hook 拦截列表，实现**系统的自我进化**。

***

## 4. Plan-and-Execute 的工业级实现：Sub-Agent 调度

视频后半段讲到了 Plan-and-Execute。这里最大的坑是 **“Planner 模型偷懒”**（只生成笼统的计划，不落地）。

**高级 Harness 的做法：Task Decomposition（任务分解）**

Harness 不是让 Planner 直接生成“写贪吃蛇游戏”，而是强制它生成 **Machine-Readable 的 DAG（有向无环图）**。

```
# Harness 期望的 Plan 输出格式（结构化）
task_id: snake_game
steps:
  - id: 1
    agent_type: architect  # 指定子 Agent 类型
    goal: Design file structure and logic flow
    dependencies: []
  - id: 2
    agent_type: coder
    goal: Implement HTML skeleton
    dependencies: [1]
  - id: 3
    agent_type: coder
    goal: Implement JS game logic
    dependencies: [2]
  - id: 4
    agent_type: tester
    goal: Run browser test and verify movement
    dependencies: [3]
```

**Harness 的调度器（Scheduler）逻辑：**

```
class Orchestrator:
    def run_plan(self, plan):
        results = {}
        for step in plan.steps:
            # 等待依赖完成
            if not all(dep in results for dep in step.dependencies):
                continue
            
            # 实例化 Sub-Agent
            sub_agent = Agent(
                role=step.agent_type, 
                tools=get_tools_for_role(step.agent_type)
            )
            
            # 执行
            result = sub_agent.run(step.goal, context=results)
            results[step.id] = result
            
            # 反馈给 Planner（Re-planning）
            if result.status == "FAIL":
                self.request_replan(step, result.error)
                
        return results
```

**这就是视频里说的“Agent 套 Agent”**：主 Agent 不干活，只负责派活和监督；干活的是被裁剪了工具集、限定了角色的 Sub-Agent。

***

## 5. 总结：Harness 的终极形态

当你把这些拼图拼起来，你会发现视频里那个“简化版 Claude Code”其实是一个 **微型操作系统**。

操作系统组件

Harness 对应物

**进程调度**​

Orchestrator (Plan & Execute)

**内存管理**​

Context Compaction & State Store

**文件系统**​

Sandboxed File Tools

**系统调用**​

Tool Invocation

**安全模块**​

Rules & Hooks (SELinux equivalent)

**日志系统**​

Observability & Tracing

**最后的硬核结论：**

**未来的软件工程师，不再是写业务逻辑的人，而是写 Harness 的人。**

业务逻辑交给模型生成，工程师的职责是确保生成过程是安全的、可控的、可追溯的，并且能在出错时优雅地恢复。

<br />

下一个挑战，我们可以深入到 **“如何设计一个支持断点续跑（Checkpointing）的 Harness 数据库 Schema”**

<br />

# 支持断点续跑（Checkpointing）的 Harness 数据库 Schema 设计

> **设计目标**：让 Agent 在进程崩溃、API 超时、甚至服务器断电后，能从**任意中断点**精确恢复到**可继续执行的状态**，而不是从头再来。

***

## 一、核心设计哲学：Event Sourcing + Snapshot

**为什么不能只存"当前状态"？**

如果只存当前状态（如 `current_step=5`），恢复时会丢失上下文历史，Agent 会因"失忆"而重复犯错。因此采用 **双轨制**：

机制

作用

存储内容

**Event Log（事件溯源）**​

完整审计链

每一步的 Thought / Action / Observation

**Snapshot（快照）**​

快速恢复

压缩后的上下文、当前状态指针

**恢复公式**：

```
最新快照 + 快照之后的所有 Event = 精确恢复现场
```

***

## 二、数据库 Schema 设计（PostgreSQL / MySQL）

### 1. 任务根表：`harness_tasks`

每个顶层任务一条记录，是整个恢复树的入口。

```
CREATE TABLE harness_tasks (
    task_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_prompt        TEXT NOT NULL,
    status             VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'paused', 'completed', 'failed', 'crashed')),
    max_steps          INT DEFAULT 100,
    current_step       INT DEFAULT 0,
    
    -- 模型与配置快照（恢复时必须一致）
    model_provider     VARCHAR(50) NOT NULL,  -- 'anthropic', 'openai'
    model_name         VARCHAR(100) NOT NULL, -- 'claude-3-5-sonnet'
    system_prompt_hash VARCHAR(64),           -- 防止 system prompt 被意外修改
    
    -- 时间追踪
    created_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at       TIMESTAMP WITH TIME ZONE,
    
    -- 元数据（用于过滤和审计）
    metadata           JSONB DEFAULT '{}',
    
    -- 约束：防止并发修改同一任务
    version            INT DEFAULT 1          -- 乐观锁
);

-- 索引
CREATE INDEX idx_tasks_status ON harness_tasks(status);
CREATE INDEX idx_tasks_created_at ON harness_tasks(created_at);
```

***

### 2. 事件表：`harness_events`（核心）

**这是 Agent 的"记忆中枢"**。每一步都不可变（Immutable）。

```
CREATE TABLE harness_events (
    event_id           BIGSERIAL PRIMARY KEY,
    task_id            UUID NOT NULL REFERENCES harness_tasks(task_id) ON DELETE CASCADE,
    
    -- 事件标识
    step_number        INT NOT NULL,          -- 第几步（全局递增）
    event_type         VARCHAR(30) NOT NULL CHECK (event_type IN (
        'thought', 'action', 'observation', 'error', 
        'human_feedback', 'system_intervention', 'checkpoint'
    )),
    
    -- 事件内容
    content            JSONB NOT NULL,        -- 结构化数据，见下文示例
    
    -- 溯源信息（用于调试和计费）
    model_used         VARCHAR(100),          -- 哪次调用用了什么模型
    token_usage        JSONB,                 -- {"input": 1234, "output": 567}
    latency_ms         INT,                   -- 本次调用耗时
    
    -- 时间戳
    created_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 确保同一任务同一步骤不会重复插入（幂等性）
    UNIQUE (task_id, step_number, event_type)
);

-- 索引：按任务和时间顺序快速查询
CREATE INDEX idx_events_task_step ON harness_events(task_id, step_number);
CREATE INDEX idx_events_type ON harness_events(event_type);
```

#### `content`字段的结构化示例：

**Action 事件**：

```
{
  "tool_name": "edit_file",
  "arguments": {
    "path": "src/main.py",
    "old_code": "def foo():\\n    pass",
    "new_code": "def foo():\\n    return 42"
  },
  "intent": "Fix return value of foo function"
}
```

**Observation 事件**：

```
{
  "tool_name": "edit_file",
  "status": "success",
  "output": "File edited successfully.",
  "diff": "--- a/src/main.py\\n+++ b/src/main.py\\n@@ -1,2 +1,2 @@\\n def foo():\\n-    pass\\n+    return 42",
  "files_changed": ["src/main.py"]
}
```

***

### 3. 快照表：`harness_snapshots`

**解决长任务恢复慢的问题**。每 N 步创建一个快照。

```
CREATE TABLE harness_snapshots (
    snapshot_id        BIGSERIAL PRIMARY KEY,
    task_id            UUID NOT NULL REFERENCES harness_tasks(task_id) ON DELETE CASCADE,
    
    -- 快照点
    at_step            INT NOT NULL,          -- 基于哪一步创建的快照
    
    -- 核心恢复数据（压缩后的上下文）
    compressed_context JSONB NOT NULL,        -- 蒸馏后的对话历史
    working_memory     JSONB NOT NULL,        -- 临时变量、中间结果
    state_flags        JSONB DEFAULT '{}',    -- 布尔状态（如 "is_test_passed": true）
    
    -- 环境指纹（恢复时校验环境一致性）
    env_checksum       VARCHAR(64),           -- 项目文件结构的哈希
    git_commit_hash    VARCHAR(40),           -- 如果有 git
    
    -- 统计
    token_count        INT,                   -- 快照时的 token 数量
    created_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (task_id, at_step)
);

CREATE INDEX idx_snapshots_task ON harness_snapshots(task_id, at_step DESC);
```

***

### 4. 工具执行记录：`harness_tool_executions`

**独立记录工具执行，用于审计和重放**。

```
CREATE TABLE harness_tool_executions (
    execution_id       BIGSERIAL PRIMARY KEY,
    task_id            UUID NOT NULL REFERENCES harness_tasks(task_id),
    event_id           BIGINT REFERENCES harness_events(event_id),  -- 关联的 Action 事件
    
    tool_name          VARCHAR(100) NOT NULL,
    arguments_hash     VARCHAR(64),          -- 参数哈希，用于幂等性检查
    
    -- 执行环境
    sandbox_id         VARCHAR(100),          -- Docker container ID 或进程 ID
    exit_code          INT,
    stdout             TEXT,
    stderr             TEXT,
    
    -- 资源消耗
    cpu_time_ms        BIGINT,
    memory_peak_bytes  BIGINT,
    
    started_at         TIMESTAMP WITH TIME ZONE,
    finished_at        TIMESTAMP WITH TIME ZONE,
    
    status             VARCHAR(20) CHECK (status IN ('pending', 'running', 'success', 'failed', 'timeout', 'killed'))
);
```

***

### 5. 人工干预表：`harness_human_in_loop`

**记录人类介入，用于恢复时重放决策**。

```
CREATE TABLE harness_human_in_loop (
    intervention_id    BIGSERIAL PRIMARY KEY,
    task_id            UUID NOT NULL REFERENCES harness_tasks(task_id),
    at_step            INT NOT NULL,
    
    intervention_type VARCHAR(30) NOT NULL CHECK (intervention_type IN (
        'approval', 'correction', 'pause', 'resume', 'abort'
    )),
    
    question           TEXT,                 -- 问人类的："是否允许 rm -rf?"
    answer             TEXT,                 -- 人类的回答
    answered_by        VARCHAR(100),         -- 操作员 ID
    answered_at        TIMESTAMP WITH TIME ZONE,
    
    -- 是否影响后续执行
    override_action    JSONB                 -- 人类指定的替代 action
);
```

***

## 三、断点续跑的恢复算法

### 场景：Agent 在第 47 步崩溃

**恢复流程**：

```
def recover_task(task_id: UUID) -> HarnessSession:
    # 1. 加载任务元数据
    task = db.fetch("SELECT * FROM harness_tasks WHERE task_id = %s", task_id)
    
    # 2. 找到最近的快照（例如第 40 步）
    snapshot = db.fetch("""
        SELECT * FROM harness_snapshots 
        WHERE task_id = %s 
        ORDER BY at_step DESC 
        LIMIT 1
    """, task_id)
    
    # 3. 加载快照后的所有事件（第 41 步到第 47 步）
    events = db.fetch("""
        SELECT * FROM harness_events 
        WHERE task_id = %s AND step_number > %s 
        ORDER BY step_number ASC
    """, task_id, snapshot.at_step)
    
    # 4. 重建上下文
    context = snapshot.compressed_context.copy()
    for event in events:
        context = apply_event_to_context(context, event)
    
    # 5. 重建 Harness 运行时状态
    harness = Harness(
        task_id=task_id,
        model=task.model_name,
        context=context,
        current_step=snapshot.at_step + len(events),
        state_flags=snapshot.state_flags
    )
    
    # 6. 校验环境一致性（可选但推荐）
    if snapshot.env_checksum != calculate_project_checksum():
        raise InconsistentEnvironmentError(
            "Project files have changed since last checkpoint!"
        )
    
    # 7. 恢复完成，准备继续
    return harness
```

***

## 四、关键工程细节（硬核部分）

### 1. 幂等性设计（Idempotency）

**问题**：恢复时可能重复执行工具（如支付、发邮件）。

**解决方案**：所有工具调用必须携带 `idempotency_key`。

```
-- 在 tool_executions 表中
ALTER TABLE harness_tool_executions ADD COLUMN idempotency_key VARCHAR(64) UNIQUE;
```

```
def execute_tool(action):
    key = f"{task_id}_{step_number}_{tool_name}_{hash(args)}"
    if db.exists("SELECT 1 FROM tool_executions WHERE idempotency_key = %s", key):
        return cached_result  # 直接返回上次结果，不真正执行
    # ... 执行工具 ...
```

***

### 2. 快照频率策略

策略

描述

适用场景

**固定间隔**​

每 10 步一个快照

简单稳定

**Token 阈值**​

上下文达 80% 窗口时快照

动态适应

**里程碑触发**​

完成关键子任务时快照

复杂工作流

**混合策略**​

以上结合

**推荐**​

***

### 3. 清理策略（防止无限膨胀）

```
-- 只保留最近 7 天的事件，但保留所有快照
DELETE FROM harness_events 
WHERE task_id IN (
    SELECT task_id FROM harness_tasks 
    WHERE status = 'completed' AND completed_at < NOW() - INTERVAL '7 days'
)
AND event_type != 'checkpoint';

-- 压缩旧快照（只保留最后一个）
WITH ranked_snapshots AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY at_step DESC) as rn
    FROM harness_snapshots
    WHERE task_id IN (SELECT task_id FROM harness_tasks WHERE status = 'completed')
)
DELETE FROM harness_snapshots WHERE snapshot_id IN (
    SELECT snapshot_id FROM ranked_snapshots WHERE rn > 1
);
```

***

## 五、总结：这个 Schema 解决了什么问题

问题

解决方案

**恢复慢**​

Snapshot 机制跳过历史重算

**状态丢失**​

Event Sourcing 完整记录

**重复执行**​

幂等键（Idempotency Key）

**环境漂移**​

Checksum 校验

**人工介入**​

Human-in-loop 表记录决策

**审计合规**​

不可变的 Event Log

**资源泄漏**​

工具执行记录 + 清理策略

**最终结论**：这个 Schema 让 Harness 从"一次性脚本"升级为**有状态、可审计、可恢复的分布式系统**。你的 Agent 不再是"跑了就跑不了第二次"的黑盒，而是一个**可以像数据库事务一样回滚和重放的可靠系统**。

<br />

<br />

