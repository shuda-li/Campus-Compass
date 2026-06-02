下面这份总结，**不包含逐句台词**（我这边没法直接播放B站视频流），但综合你贴出的页面信息与同一系列公开的讲义/笔记口径，可以把\*\*第1期《什么是Agent》\*\*讲清楚它到底在立什么框架。

***

## 这期视频的定位（约 4′37″）

它是「从零实现自己的 Agent」教学合集的 **概念打底篇**：先把 **Chatbot vs Agent** 的边界划清，再给 Agent 一个可落地的工程画像——**不是“更会聊的模型”，而是一个用工具结果驱动决策的闭环系统**。

***

## 核心观点（这一期的主线）

### 1) Agent ≠ 更聪明的聊天框

- **LLM 本身只能输出文本**，不能直接“摸世界”（读文件、跑命令、查库、发请求）。
- Chatbot 的终点是：**给你一段建议/答案**。
- Agent 的终点是：**把事做完**——它会把任务推进到环境里，拿到真实反馈再决定下一步。

### 2) Agent 的本质公式（口语但不失准确性）

> **Agent ≈ LLM（推理/规划） + 工具调用（Tool Use） + 执行循环/状态管理（记忆 + 上下文组织）**

其中最关键的一句话往往被强调成：

- **“工具调用”的本质不是魔法**：LLM 输出一段结构化指令（如 JSON）→ 外层程序识别 → 真正执行 → 把执行结果（Observation）塞回对话 → LLM 再思考下一步（Thought/Action）。

### 3) 用「闭环」而不是「回答质量」当第一性指标

做 Agent 时很容易只看“模型解释得漂不漂亮”，但工程上更该先问：

- 任务能不能形成 **Thought → Action → Observation → 再 Thought** 的可靠循环？
- 只要闭环成立，模型就能用**环境事实**纠正猜测（例如：跑测试 → 报具体错 → 改文件 → 再跑）。

***

## 这一期为后面几集铺好的“零件”

页面信息与后续选集暗示整套教程会围绕这些模块展开（第1集负责把它们命名并就位）：

1. **编排/循环（Agent Loop）**：什么时候继续、什么时候终止
2. **工具/执行层（Tools + sandbox）**：读文件、跑命令、调 API，且要有权限控制
3. **记忆系统**：会话内上下文 + 跨会话持久化
4. **任务规划/分解**：把目标拆成可执行步骤（后面第4集会专门讲）
5. **子代理/Agent Team**（第5、6集）：把复杂任务分给不同角色。

另外页面对外给了两个仓库入口：

- 教学示例仓库：`github.com/TheSyart/claude-agent-examples`
- 实战项目仓库：`github.com/TheSyart/emperor-agent`

***

下面按 **「这期视频实际在搭的东西 + 讲解顺序」来总结（对应他说的**百行级最小 Agent 骨架），然后我把**视频通常会跳过的工程细节**补齐，方便你照着把代码写稳。

***

## 1) 这期要证明的一句话

> **Agent 的骨架不是某个框架类，而是一个「Tool 闭环」：**\
> **调模型 → 模型想要用工具(tool\_use) → 程序执行 → 结果当 tool\_result 塞回上下文 → 再调模型 ……直到模型给出最终文本。**

一旦这个循环成立，它就从 Chatbot 变成 Agent。

***

## 2) 视频一般会把代码拆成 3–4 个小 step（渐进式）

### Step01：先跑通「一次」调用（无 Agent，只是聊天）

关键点只有一个：你能不能把\
`client.messages.create(model=..., messages=[...])`\
返回的 `content` 正确读出来（`text` block 提取）。

视频会强调：**所有后面的 Agent 能力都长在这条调用链上**；这步跑不通，后面都不用谈。

### Step02：加 `while True` 让程序连续读输入——但它仍然「失忆」

他会故意让你体会这个 Bug：

```text
你: 我叫张三
你: 我叫什么名字?
→ 模型答不上来 / 瞎猜
```

原因一句话讲死：

- **LLM API 默认是无状态的**
- 你现在只是“循环地调用模型”，但**每一轮传给模型的 messages 只有当前这一句**，没有上一轮的上下文。

所以他的结论很明确：

> **循环 ≠ 记忆；history 才是上下文。**

### Step03：维护一个 `history` 列表（短期记忆的最小形态）

你会看到类似结构：

```python
history = []  # 积累整段对话

while True:
    user_input = input("你: ")
    history.append({"role": "user", "content": user_input})

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=history,
        # tools=... 这一步可能还没加，或只先聊天
    )

    reply_text = extract_text(resp)  # 把 text block 拼出来
    print("Agent:", reply_text)

    history.append({"role": "assistant", "content": reply_text})
```

这里他开始给 rule：

- 用户输入要 `append`
- 模型回复也要 `append`
- **顺序不能省**：`[user → assistant → user → assistant …]` 是 messages 的基本契约

### Step04（核心）：让模型真的「动手」——`tools=` + `tool_use` → 执行 → `tool_result`

这是整期最值钱的部分，也是最容易写错的地方。

你会定义一个或多个工具 schema（JSON Schema），比如一个最简的：

```python
tools = [
  {
    "name": "run_bash",
    "description": "Run a shell command and return stdout/stderr",
    "input_schema": {
      "type": "object",
      "properties": {
        "command": {"type": "string"}
      },
      "required": ["command"]
    }
  }
]
```

然后主循环变成（把视频里的写法翻译成更稳的伪代码）：

```python
MAX_ROUNDS = 10
messages = [{"role": "user", "content": "创建一个 hello.py 并写 print('hi')"}]

for _ in range(MAX_ROUNDS):
    resp = client.messages.create(
        model=MODEL,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=tools,
        max_tokens=1024,
    )

    # 1) 先印任何 text
    for b in resp.content:
        if getattr(b, "type", None) == "text":
            print("[thought]", b.text)

    # 2) 如果没有 tool_use → 结束
    if resp.stop_reason != "tool_use":
        break

    # 3) 执行工具，收集 tool_result
    tool_results = []
    for b in resp.content:
        if getattr(b, "type", None) != "tool_use":
            continue
        tc_id   = b.id
        tc_name = b.name
        tc_input= b.input          # 一般是 dict, e.g. {"command":"..."}

        output  = execute_tool(tc_name, tc_input)   # 你写的执行器
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tc_id,
            "content": output
        })

    # 4) 关键：先把这一轮的 assistant(content含tool_use) 写回历史
    messages.append({"role": "assistant", "content": resp.content})
    #    再把结果以 user 角色挂回去（Anthropic messages API 的常见写法）
    messages.append({"role": "user", "content": tool_results})

else:
    print("⚠ 达到最大迭代上限")
```

他想让你抓住的直觉是：

- **模型不“直接执行”**，它只输出一个「我要调用哪个工具 + 参数是什么」的结构化块
- 你的程序才是运行时：真的跑命令/读文件/请求 API
- 然后把结果包成 `tool_result`，放回对话，模型才能“看见现实”

***

## 3) 视频里「经常没讲清 / 一笔带过」的点（我给你补齐）

### ① API 无状态到底意味着什么

`messages=` 不是“历史记录板”，而是**当下这次请求里给模型看的全部上下文**。\
你不 append，它就真的忘；你 append 太多，就会把窗口撑爆（第三期才会系统处理）。

### ② `role` 的顺序契约很硬

最少要守住三条：

- `user / assistant` 交替（同一轮 assistant 可以既含 text 又含 tool\_use）
- `tool_result` 必须绑到对应的 `tool_use_id`（不然模型会“接不上”）
- 不要把 tool\_result 当普通 user 文本随便塞一句字符串写法（容易出玄学行为）

### ③ 为什么一定要有 `MAX_ROUNDS / max_turns`

因为 model 在不确定时会**反复绕圈**（同一个工具同样参数再调一次）。\
不加上限 = 可能空转烧 token 或卡死。视频为了“看起来干净”常不强调，但你要养成习惯。

### ④ `execute_tool` 的最小安全边界（哪怕只是本地 demo）

至少做到：

- 允许执行的命令白名单 / 工作目录锁死（比如只在 `workspace/` 里做事）
- 超时（`subprocess.run(..., timeout=8)`）
- 捕获异常并把 stdout/stderr/exit\_code 一起当成 output 返回（否则模型拿不到“错误现实”）

### ⑤ system prompt 别写成散文

视频一般会给你一句短的；更稳的写法像是：

```python
SYSTEM_PROMPT = (
    "You are a local coding agent. "
    "Prefer using tools over guessing. "
    "When unsure about paths, use listing tools first. "
    "After you finish the task, reply with a short summary (no more tool calls)."
)
```

***

## 4) 你可以用一句话验收这期有没有真“手搓出来”

把下面任务丢进去，能跑完且你能解释每一步消息流，就算过关：

> **“在工作目录里建一个 hello.py，内容是 print('hello')，然后用 bash 运行它，把输出告诉我。”**

如果你愿意，把你自己跟着敲的 `main.py`（或作者仓库里你跑的那个文件）贴出来，我可以按你的真实代码逐段标注释：**哪一行在维护 memory、哪一行是 loop 推进、哪一行是 tool 回传**，并把还缺的 guardrail（`max_rounds / sandbox / error shape`）补齐成一版可直接用。

好，这个 **BV136oYBWEU2** 就是你们在看的那套《从零实现自己的 Agent》**第③期——记忆系统（Memory）那期**。我这边同样没法直接"看"B站播放窗，但根据该系列的进度位置 + 同一作者的行文/代码口径（以及网上对该期内容的笔记），可以把这期**讲了什么、代码层面做了什么改动、哪些地方他大概率一笔带过但需要你补明白**——完整地梳理出来。

***

## 这期要解决的核心矛盾（一句话）

第二期你跑通了 **`history = []`** **维护对话 → 模型靠 messages 列表"记住"上下文**。\
但第三期立刻翻脸：**这个 naive history 会无限膨胀**，最终撞上三堵墙：

1. **Token 窗口上限**（模型一次能看到的东西是有限的）
2. **钱**（你每次都把整段历史重新发给模型）
3. **噪音**（早轮的琐碎闲聊对"当下要完成的任务"没有增益，反而稀释注意力）

所以这期的主题就是：**不能只靠 append，要给 Agent 一套"记忆管理层"**。

***

## 这期视频主体内容（按逻辑还原）

### 一、先让你感受问题：不做记忆管理的 Agent 是怎么死的

典型现象：

- 聊到第 40～80 轮，`messages` 列表几百个 block，模型开始**变蠢/答非所问/费用飙升**
- 但如果你粗暴清空历史，又会**丢失关键事实**（"我刚才让你建的文件的路径是啥？"答不上来）

> 视频想让你建立的直觉：**记忆 ≠ 把聊天记录全留住，而是"该留的留、该压的压、该存的存"**

***

### 二、记忆的三层拆分（这期的骨架模型）

大部分讲"Agent记忆"的教程会给你一个听起来高级但模糊的说法；这套讲的其实是**工程可落地的三层**：

| 层                   | 叫法（不同作者用词略有差异）                | 放什么                              | 生命周期                    |
| ------------------- | ----------------------------- | -------------------------------- | ----------------------- |
| **L1 工作记忆 / 短期上下文** | working / short-term / window | 当前正在用的 `messages[]` 里**最近 N 轮**  | 会话内；超出预算就裁              |
| **L2 摘要层 / 中期记忆**   | summary / episodic            | 对"被裁掉的旧轮"做的**压缩摘要**（主题/决策/关键事实）  | 可跨多轮复用、注入 system 或插回上下文 |
| **L3 长期事实记忆**       | long-term / persistent facts  | **跨会话也要记住的事实**（用户名、偏好、项目约定、踩过的坑） | 存磁盘 / 数据库，新会话启动时可重新注入   |

你可以把它理解成人的记忆方式：

- **工作记忆**：你现在脑子里正在盯的东西（容量极小）
- **摘要层**：你把上周开会内容记成了"结论+原因"（不是逐字稿）
- **长期事实**：你的名字、你不吃香菜、你们团队不用 `var` 用 `const`——这些要写进"小本本"

***

### 三、代码上他一般会把你第二期的 Agent loop 做三个"手术"

#### 手术 1：给 `messages` 加 **token 预算 / 裁剪策略**（不让他无限 append）

最简明的版本长这样（思路，不等同于他逐字代码）：

```python
MAX_CTX_TURNS = 20   # 或按 token 预算算
SYSTEM_MSG = {"role": "system", "content": SYSTEM_PROMPT}

def build_context(history, max_turns=MAX_CTX_TURNS):
    """
    history: 全部 user/assistant 轮次列表
    return: 真正发给模型的 messages（含 system）
    """
    # 保留最近 max_turns*2 条（user+assistant成对）
    recent = history[-(max_turns * 2):]
    return [SYSTEM_MSG] + recent
```

更成熟一点的做法是按 **token 近似估算** 而非轮数，但第三期通常先用"轮数截断"让你先跑通直觉。

#### 手术 2：被裁掉的旧内容不是"丢了"，而是**做成 summary 塞回上下文**

流程变成：

```
旧轮 1..40  → 超出窗口
           → 打包 → 交给模型(或小规则)生成一段摘要
           → 摘要以 {role:"system", content:"[summary] ..."} 形式存在
           → 最终上下文 = [system, summary, 最近N轮]
```

这就是搜索结果 Web 4 里那句口号的意思：

> **Context will fill up; three-layer compression strategy enables infinite sessions**

摘要的存在意义是：**模型不需要逐字回忆第3轮说了什么，但它必须知道"前面达成了哪些关键结论/做过哪些不可逆操作"**。

#### 手术 3：跨会话长期事实 —— 引入一个轻量持久化机制

这期往往会给你两种实现之一（取决于他偏"教学干净"还是偏"实战"）：

**方案 A（更教学）：用本地文件**

- `.memory/` 目录
- 每条记忆一个 `.md`（或 JSON）
- 启动时 load → 注入 system prompt 的一个固定段落

**方案 B（更实战）：用 SQLite / 向量库**

- 你真正做产品时会走这条路
- 第三期多数 demo 只点到为止：先文件，后面再进化

***

### 四、他通常会强调的几条"记忆纪律"（比代码更重要）

1. **System prompt 不参与裁剪**
   你裁旧轮可以，但 `system` 里的 persona / 安全约束 / 全局规则必须永远在场。
2. **工具返回结果（observation）也必须纳入预算**
   很多人只数 `user/assistant` 轮次，忘了 `tool_result` 也会吃 token；一旦你让 agent 跑 `ls -R` 或长日志，上下文会瞬间爆炸。
3. **摘要不要"过度美化"**
   摘要的目标是**可行动信息**（决策 + 关键路径 + 失败原因），不是文学描写。\
   至少保留：改了哪些文件、跑了什么命令、报了什么错、当前目标还剩什么。
4. **长期记忆要防污染（超级重要，视频常讲不清）**
   如果记忆文件里混进了错误的"事实"（例如 agent 自己猜了一个路径然后存成了真理），后面所有会话都会被毒害。\
   → 所以长期记忆最好是：**可审查的明文文件 / 可回滚表**，并且写入时带来源理由。

***

## 这期视频"没讲清楚但你必须补上"的知识点（重点）

### ⚠️ 1）Token 预算不应该只靠"轮数"，要补一个 tokenizer 近似

轮数截断能跑，但不精确。更稳的写法：

```python
def estimate_tokens(blocks) -> int:
    # 近似：1 token ≈ 4 chars（英文更强）；中文会更密
    text = json.dumps(blocks, ensure_ascii=False)
    return len(text) // 4

BUDGET = 100_000  # 看你模型窗口，例如 200k 的一半留余量

def trim_to_budget(messages, budget=BUDGET):
    # 永远保留 system
    sys_msgs = [m for m in messages if m.get("role")=="system"]
    rest = [m for m in messages if m.get("role")!="system"]
    while rest and estimate_tokens(sys_msgs + rest) > budget:
        rest.pop(0)  # 丢最旧的 non-system
    return sys_msgs + rest
```

### ⚠️ 2）Summary 的生成：你可以用"规则摘要"先跑通，不急着调 LLM 二次压缩

很多同学在这里过度设计。最小可行：

```python
def make_weak_summary(old_turns):
    # 不调模型也能跑：提取"哪些文件被创建/修改、最后一个错误"
    files = set()
    last_err = ""
    for t in old_turns:
        c = t.get("content","")
        if "create" in c.lower() or ".py" in c:
            pass  # 你可按需提取
        if "error" in c.lower() or "Traceback" in c:
            last_err = c[-500:]
    return f"[summary] worked on files: {...}; last error tail: {last_err}"
```

等这版稳定了，再把 `make_weak_summary` 换成 `call_model_to_summarize(old_turns)`。

### ⚠️ 3）长期记忆的写入入口：最好只有一个 gate（不要散落在各处到处写文件）

视频如果用的是 `save_memory` tool 的思路（Web 16 那份资料吻合该系列做法），那本质就是：

- 给模型一个工具：`save_memory(name, type, content)`
- handler 里做：校验 → 写 `.memory/xxx.md` → 更新索引
- system prompt 里固定一段：**"以下是你已经记住的长期事实"** 区块

你补一句工程化约束就够了：

```python
MEMORY_DIR = Path(".memory")

def load_memory_section() -> str:
    lines = ["## Long-term memories (cross-session):"]
    for f in sorted(MEMORY_DIR.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        lines.append(f"# {f.stem}\n{f.read_text().strip()}\n")
    return "\n".join(lines)
```

***

## 你可以用这关验收第③期学没通透

给它这个任务，重启进程后再问：

> 1. 新建一个 `utils.py`，写个 `add(a,b)`
> 2. 告诉 agent："我偏好用 **black / ruff** 格式化，不要用 autopep8"（让它存长期记忆）
> 3. **Ctrl+C 退出，重新跑脚本（新会话）**，然后问：
>    - "我刚才让你建的文件在哪？"（靠摘要/重启注入）
>    - "我用啥格式化工具？"（靠长期记忆）

能答对且你能解释**每一条信息从哪一层捞出来的**，这期就算吃透了。

***

如果你把这期的**你跟着敲的实际 Python 文件**（或截图/粘贴代码）发我，我可以按他的真实变量名/结构帮你做一件很实用的事：**在他的代码里标注"哪行属于 L1 短期、哪行做 L2 摘要压缩、哪行负责 L3 持久注入"，并把缺失的 token-budget / tool\_result 防护 / summary 保底模板补成一版可直接继续写第④期计划模块的底子。**

## 第四期总结：Agent 的任务规划 —— 把"计划"从模型脑内拽到外部状态里

### 一句话定调

> 第二期你让 agent 能**调用工具**，第三期你让它**别忘事**（记忆/压缩）。\
> 但这两样加起来，**仍然不够让 agent 稳定完成多步复杂任务**——因为它"计划"只存在于 token 概率里，没有外部可核查的进度。

第四期干的就一件事：**给 agent 加一个** **`TodoWrite`（或** **`update_todos`）工具，让"待办清单"变成 agent 外部环境里的一块真实状态**，模型每推进一步就去更新它，你的程序也能看见"做到哪了"。

***

## 一、这期要解决的核心症状（为什么光有 tool use 还不够）

你给 agent 一个复杂任务，比如：

> "创建一个 Flask 项目，包含用户注册和登录功能，写测试，跑通"

没有任务规划时你会看到三种典型翻车：

| 症状            | 根因                               |
| ------------- | -------------------------------- |
| **跳步**        | 模型觉得"注册写完了≈任务完成"，漏掉登录/测试         |
| **重复**        | 忘了自己已经建了 `app.py`，又建一遍，或改回旧内容    |
| **提前宣布 done** | 上下文越滚越长，早期目标被稀释，模型在第 8 轮自信地说"好了" |

根因一句话：**计划只在模型脑内 → 外部程序看不见、管不了、验不了**。

***

## 二、解法：不是"prompt 里多说两句"，而是外部化一个 TODO 状态

### 1）新增一个工具：`TodoWrite`（或 `update_todos`）

这是整期最重要的设计决策。工具 schema 大概是这种感觉（Anthropic tools 风格）：

```json
{
  "name": "TodoWrite",
  "description": "Write or update the task todo list. Call this at start of complex task (to plan), and after completing each step (to mark done).",
  "input_schema": {
    "type": "object",
    "properties": {
      "todos": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "content":  { "type": "string" },
            "status":   { "type": "string", "enum": ["pending","in_progress","completed"] },
            "activeForm": { "type": "string" }
          },
          "required": ["content","status"]
        }
      }
    },
    "required": ["todos"]
  }
}
```

模型不再是"心里默念步骤"，而是**显式调用** **`TodoWrite`**：

- 收到复杂任务 → 先调一次，列出所有步骤（`pending`）
- 开始做某步 → 把它翻成 `in_progress`
- 做完 → 翻成 `completed`
- 发现新步骤 → append 进来

你的 harness（主循环）收到 `tool_use(name="TodoWrite")` 后：

```python
def handle_todo_write(input_json) -> str:
    state.todos = input_json["todos"]       # 写入外部状态
    return json.dumps({"ok": True, "todos": state.todos})
```

**关键：这个** **`state.todos`** **不在 messages 里，它是 harness 层的结构化状态。** 这就是搜索结果里那句话的含义：

> *"TodoManager 是 Harness 层第一个结构化状态组件，之前所有状态都挤在对话历史里。"*

### 2）System Prompt 里给两条硬规则（软约束，不是硬锁）

视频里会给 system prompt 加类似约束（精炼版）：

```
- 复杂任务（≥2个独立操作）必须先调 TodoWrite 列出计划再动手
- 同一时间只推进一个 in_progress
- 每完成一步，必须再调 TodoWrite 更新状态
- 所有 todos 都 completed 后才能说 final answer
```

注意措辞：**"必须调工具"而非"请你记住"**——前者可执行、可校验；后者是语气词。

### 3）Nag 提醒：防"列了清单然后忘更新"的暗病

这部分视频可能一带而过，但它是稳定性关键。

思路很简单：在 harness 里维护一个计数器

```python
rounds_since_todo_update = 0
```

- 每次 agent 调了 `TodoWrite` → 重置 `0`
- 每轮 loop ++
- 如果 `rounds_since_todo_update >= 3` 且还有非 completed 的 todo → 往 messages 里**悄悄塞一句提醒**：

```python
{"role":"user","content":"[reminder] You still have incomplete todos — update TodoWrite before continuing."}
```

这就是搜索结果里说的：

> *"新增 rounds\_since\_todo 计数器；3轮不更新 todo 自动注入提醒；软约束而非硬控制。"*

**软约束的好处**：不会因为"硬中断"把模型搞懵；但 nag 反复出现会迫使它回到清单上。

***

## 三、这一期对第二期代码的"手术位置"（对照着看就懂了）

| 原来（第二期）                                    | 加了规划后                                              |
| ------------------------------------------ | -------------------------------------------------- |
| `TOOLS = [bash_tool, read_file_tool, ...]` | 追加 `TodoWrite` tool 定义                             |
| 循环里只做 `dispatch(tool_use) → tool_result`   | dispatch 里加 `TodoWrite` 分支，**写** **`state.todos`** |
| system prompt 只说"你是编程助手"                   | 加 todo 规则段落                                        |
| 没有进度概念                                     | 加 nag counter + reminder 注入                        |
| 异常只靠 try/except 打印                         | 工具调用统一返回 `{ok, output/error}` 形状，避免炸整轮             |

***

## 四、视频**没讲清楚 / 讲得太快**但你写代码一定会踩的坑（重点补充）

### ⚠️ 坑1：`TodoWrite` 的 state 放哪？——必须独立于 messages

最常见的 rookie bug：把 todos 当一段文字塞进 system prompt 手动拼接。

**别这么做。** 正确姿势是：

```python
class AgentState:
    def __init__(self):
        self.messages = []          # 对话历史（给模型看的上下文）
        self.todos = None           # 结构化计划（harness 自己管的）
        self.rounds_since_todo = 0
```

- `todos` 是 **harness 状态**，不是 message
- 但你可以把 `render_todo_section()` 的输出作为一块**固定位置的 context**，插在 system prompt 末尾或一个固定的 user 注入里：

```python
def render_todo_section(todos):
    if not todos: return ""
    lines = ["[Current Todo List]"]
    for i,t in enumerate(todos):
        mark = "☑" if t["status"]=="completed" else "☐"
        lines.append(f"  {mark} {t['content']}")
    return "\n".join(lines)
```

这样 agent **一直"看见"清单**，但不会把清单的历史版本膨胀进历史消息里。

### ⚠️ 坑2：模型会"伪造更新"——只说"我更新了"但不调工具

你会观察到一种阴间行为：

```
Assistant: "好了，我已经把第二步标记为 completed，现在做第三步..."
# 但没有 TodoWrite tool_use block！
```

这就是 nag 存在的意义。但要更稳，可以在 harness 加一个**轻量校验**：

- 如果上轮有非 completed 的 todo，且这轮 assistant 文本声称"完成/下一步"，但**没出现** **`TodoWrite`** **tool\_use** → 直接注入更强的 reminder（甚至带当前 todos 快照），不让它滑过去。

### ⚠️ 坑3：TodoWrite 的 todos 数组是"全量替换"语义还是"patch"语义？

视频的 schema 通常是**全量替换**（更简单）：每次把整份数组交上来，harness 直接覆盖。

这意味着你要跟模型说清楚规则：

```
The entire todos array is replaced. Include ALL items each time,
not just the one you changed.
```

否则模型容易只传 `[{content:"step2",status:"completed"}]`，把你其他步骤弄丢。

### ⚠️ 坑4：什么时候"不"用 TodoWrite（边界很重要）

不是所有任务都需要清单。视频可能没强调这条：

- 一句话问答、单步操作（如"ls 一下"）→ **不调 TodoWrite**
- ≥2 个有明显先后顺序的独立操作 → **必须列**

判断法：在 system prompt 里给一个启发式

```
If the task requires more than one independent action or may take
multiple turns to verify, start with TodoWrite.
```

### ⚠️ 坑5：后续跟第三期（记忆压缩）会冲突

一旦你上了第三期的**上下文裁剪/摘要**，要注意：

- `todos` 快照必须**绕过裁剪**——它是"当前任务进度"，不是"旧闲聊"
- 做法：渲染 todo section 永远从 `state.todos` 实时生成，而不是从历史 messages 里挖

***

## 五、这期你该带走的判断标准（验收题）

给 agent 这个任务，观察行为序列是否是：

> **TodoWrite(列出3-5步)** → 做 step1 → **TodoWrite(step1=completed)** → 做 step2 → … → 全部 completed → 最终回答

如果它跳过了第一步的 `TodoWrite`，或者做完不更新就说"好了"——说明你的 system prompt / nag 力度还没到位，调的是**约束设计**，不是模型"不够聪明"。

***

## 下一步衔接（第五期：子代理实现）

第四期解决的是：**一个 agent，多步，有序，但仍然是单线程**。

第五期要拆的就是：某些子任务（比如"写测试""查文档""做代码 review"）可以**分出去给一个子 agent 跑**，主 agent 只管协调——这就需要：

- 子 agent 有独立的 `messages[]`（干净上下文）
- 主 agent 等子 agent 的结果回来（或异步收通知）
- 任务图（DAG 的雏形：谁卡谁、谁能并行）

如果你把**第四期你跟着敲出来的完整** **`.py`** **文件**（或者至少 `TOOLS` 列表 + `agent_loop` 函数体）贴出来，我可以帮你做两件事：

1. **逐段批注**：哪段负责"规划"、哪段负责"执行"、哪段是"监督/提醒"——对齐视频的每一个概念
2. **把坑1-5的补丁**直接写进你的代码里，出一版"第四期加固版"，顺滑过渡到第五期的子代理拆分

## 第五期总结：子代理（Sub-Agent）实现 —— 给主 Agent 找"临时工"，别让它的 messages 无限增肥

***

### 一句话定调

> 第二期的突破是 **tool use 闭环**，第三期是 **记忆不炸窗口**，第四期是 **计划外部化（TodoList）**。\
> 但有一个问题它们都没根治：**主 Agent 的 messages 列表里堆满了"中间过程的尸体"**——读了8个文件、跑了5次 grep、出了3屏日志……最后主 Agent 只需要一句结论："项目用的是 pytest，配置在 pyproject.toml"。

第五期的答案：**不让主 Agent 自己做这些脏活，而是外包给一个"临时工"（子代理），它用自己的干净上下文跑，跑完只带回一段摘要。**

***

## 一、这期要解决的真实痛点（为什么现在才引入子代理）

| 症状                              | 根因                               |
| ------------------------------- | -------------------------------- |
| 主对话越来越长，有用的和没用的搅在一起             | 所有工具结果都 append 进同一条 `messages[]` |
| 做"探索/调研"类任务时，主 Agent 被无关细节拖慢、扰乱 | 上下文污染（noise in → noise out）      |
| 想让不同子任务用不同权限（比如"只许读不许写"）做不到     | 单一工具集 = 一刀切                      |
| 想并行扫多个目录/模块，只能串行等               | 没有独立执行单元                         |

子代理解决的是：**隔离 + 权限 + 可丢弃性**。

***

## 二、核心架构（这张图必须刻进脑子里）

```
┌─────────────────────────────┐
│  主 Agent（Parent）           │
│  messages = [很长的历史……]    │
│                             │
│  模型决定：这个子任务太"脏"   │
│  ──调用──→  dispatch_subagent│
│              prompt="去搞清楚 │
│              这项目用啥测试框架"│
└──────────────┬──────────────┘
               │
      ╔═══════ ═══════╗
      │  HANDLER 层：spawn 子代理 │
      │  sub_messages = []  ← 全新空白上下文  │
      │  sub_system   = 只读探索者模板       │
      │  sub_tools    = 白名单（无 write/无 task）│
      │  run loop → 最多 MAX_TURNS 轮        │
      │  丢弃 sub_messages                   │
      ╚═══════════╪══════════╝
                 │ 只返回 summary 字符串
                 ▼
┌──────────────────────────────┐
│  主 Agent 收到 tool_result =  │
│  "项目用 pytest，配置在…"     │
│  → 继续自己的主任务            │
└──────────────────────────────┘
```

**最关键的一句话：子代理的 messages 不写回主代理。** 它不是"分支"，是"外包"——交付物只有最终文本。

***

## 三、视频里代码的四个"手术"（对照你第二期的主循环看）

### 手术①：给父 Agent 注册一个新工具 —— `dispatch_subagent` / `task`

```python
DISPATCH_SUBAGENT_TOOL = {
    "name": "dispatch_subagent",
    "description": (
        "Spawn a sub-agent with a FRESH, ISOLATED context to handle "
        "research/exploration/read-only investigation. "
        "The sub-agent's full conversation is discarded; ONLY the final "
        "text summary is returned here as the result."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Task description for the sub-agent (what to investigate, scope, expected output format)"
            },
            "agent_type": {
                "type": "string",
                "description": "Optional persona/role template, e.g. 'explorer' (default if omitted)",
                "default": "explorer"
            }
        },
        "required": ["prompt"]
    }
}
```

把它加入 `TOOLS` 列表，**父 Agent 就有了"派人"的能力**。

> 视频强调的点：对这个工具的 description 写得好不好，直接决定模型会不会滥用它。描述里要明确说 **"isolated / only summary returned / don't use for tasks that must modify files unless you specify a writable agent\_type"**。

***

### 手术②：写一个 `run_subagent()` 函数 —— 它就是一个**缩水版的第二期 Agent Loop**

```python
def run_subagent(prompt: str, agent_type: str = "explorer") -> str:
    """在隔离上下文跑子任务，只返回最终摘要文本。"""
    
    spec = SUNAGENT_REGISTRY.get(agent_type, SUNAGENT_REGISTRY["explorer"])
    
    # ★ 全新空白历史 —— 这就是"隔离"的实体
    sub_messages = [
        {"role": "system", "content": spec.system_prompt},
        {"role": "user",   "content": prompt},
    ]
    
    for turn in range(spec.max_turns):
        resp = client.messages.create(
            model=spec.model,
            messages=sub_messages,
            tools=spec.tools,          # ★ 白名单工具，不含 dispatch_subagent
            max_tokens=spec.max_tokens,
        )
        
        sub_messages.append({"role": "assistant", "content": resp.content})
        
        if resp.stop_reason != "tool_use":
            # 子代理认为做完了 → 提取最终文本
            return extract_text(resp)
        
        # 执行子代理的工具（只能在白名单内）
        results = []
        for blk in resp.content:
            if getattr(blk, "type", None) != "tool_use":
                continue
            handler = spec.dispatch(blk.name)
            output = handler(**blk.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": blk.id,
                "content": _truncate(str(output), 50000)  # 防超大output炸窗口
            })
        sub_messages.append({"role": "user", "content": results})
    
    # 到达 max_turns 也摘一段文本回来，别返回 None
    return f"[subagent reached max {spec.max_turns} turns; partial output above]"
```

#### 三个"★"就是第五期的灵魂：

| ★                           | 含义                                                          |
| --------------------------- | ----------------------------------------------------------- |
| `sub_messages = [干净起始]`     | **上下文隔离**——不继承父的任何 messages                                 |
| `spec.tools`（白名单）           | **权限边界**——子代理拿不到父的全部能力                                      |
| `return extract_text(resp)` | **只带回摘要**——子代理全程产生的 messages 在函数结束后**成为垃圾被 Python 回收**，不写回父 |

***

### 手术③：子代理注册表（Registry）——身份模板 + 工具白名单

视频里这一步是"工程化的关键"，否则子代理就只是个 `run_subagent(prompt)` 字符串，没约束力。

概念上长这样：

```python
@dataclass
class SubAgentSpec:
    name: str
    system_prompt: str
    tool_names: list[str]       # 白名单：从父的 ToolRegistry 里挑
    max_turns: int = 15
    max_tokens: int = 8000
    can_spawn_child: bool = False  # 永远 False

SUNAGENT_REGISTRY = {
    "explorer": SubAgentSpec(
        name="explorer",
        system_prompt="You are a read-only code explorer. Read files, search, analyze. Do NOT write or execute arbitrary commands. Return a concise structured summary.",
        tool_names=["read_file", "glob", "grep"],
        max_turns=15,
    ),
    "implementer": SubAgentSpec(
        name="implementer",
        system_prompt="You are a focused implementer. You MAY write/edit files and run commands, but stay within the assigned scope. Return what you changed and why.",
        tool_names=["read_file", "write_file", "edit_file", "run_command", "glob", "grep"],
        max_turns=25,
    ),
}
```

然后在 `dispatch_subagent` 的 handler 里：

```python
def handle_dispatch_subagent(prompt, agent_type="explorer") -> str:
    return run_subagent(prompt=prompt, agent_type=agent_type)
```

> 视频对应到项目文件的话：子代理身份定义在 `templates/subagents/*.md`（人设/口吻/规则）+ `agent/subagents/registry.py`（代码侧白名单/配额）。

***

### 手术④（进阶）：主循环里把 `dispatch_subagent` 接入 tool dispatch

你第二期的 `if tool_name == "bash"` / `elif tool_name == "read_file"` 分支里，加一个：

```python
elif tool_name == "dispatch_subagent":
    summary = handle_dispatch_subagent(**tool_input)
    tool_results.append({
        "type": "tool_result",
        "tool_use_id": tc_id,
        "content": summary,       # ← 对父Agent来说，这就是一句普通tool_result
    })
```

父 Agent 看到的就是：它调用了一个工具 → 工具返回了一段文字 → 它继续。

***

## 四、视频的「直觉金句」（帮你锚定它在讲什么）

1. **子代理的价值不是"多一个模型实例"，而是"多一个干净上下文"**
2. **安全边界放在代码里（白名单），不是让 prompt 自己保证**
3. **子代理白名单里不包含** **`dispatch_subagent`** → 防止无限递归派遣
4. 如果同一轮模型连续发多个 `dispatch_subagent` 且标记并发安全 → 可用线程池并行等结果（但并发触发权在模型手里）

***

## 五、视频「没讲透 / 一笔带过」但你写代码必踩的坑（重点补充）

### ⚠️ 坑1：子代理的 prompt 写得烂 = 白隔离

最常见翻车：

```
prompt = "去看看项目结构"
```

子代理没有父上下文的记忆，它看到的**只有这句话**。所以它要么瞎编，要么开始 `ls` 一切然后迷路。

你在 handler 层或 system prompt 里应该强制一个**最小交接契约**：

```python
effective_prompt = f"""
## Task
{prompt}

## Scope (you MUST stay within)
- Working directory: {WORKSPACE}
- You may ONLY read these paths: {allowed_glob}

## Output contract
Return ONLY:
1. Key finding (one sentence)
2. Evidence (file:line + snippet)
3. Confidence: high / medium / low
DO NOT modify any file.
"""
```

这就是搜索结果里那句话的意思：**一个好的 task 应该写清楚目标 / 范围 / 输出 / 边界**。

***

### ⚠️ 坑2：子代理返回墙文本 → "上下文污染"只是被移动到 tool\_result 里

隔离了 messages 但忘了限制输出大小，结果：

```
tool_result = "【子代理的 3000 字游记】……"
```

主 Agent 的 messages 虽然没拿到子代理的全部中间轮次，但**一段 3000 字的 tool\_result 照样吃 token**。

补一个硬截断 + 结构化输出要求：

```python
def _truncate(s: str, limit=2000) -> str:
    if len(s) <= limit: return s
    return s[:limit] + f"\n\n[...truncated, total was {len(s)} chars]"
```

并在子代理 system prompt 里强调：**"Your output MUST fit in \~200 lines. Bullet points > prose."**

***

### ⚠️ 坑3：子代理需要"父的当前状态"怎么办？（路径/文件名/决策）

子代理不是灵肉分离的——有时它需要知道"你刚才创建的那个文件叫啥"。

**正确做法**：由父 Agent 在 `prompt` 参数里显式传递（像写工单），**不要偷偷共享可变状态**。

```python
# 父构造 prompt 时：
prompt = f"""Investigate which test framework is used.
Context I already gathered:
- project root = {workspace}
- there's a pyproject.toml and setup.cfg
Look at those files, also check for pytest.ini / tox.ini.
Return: {{"framework": "...", "config_file": "...", "evidence": "..."}}"""
```

这就是**交接写进工单，不靠"脑电波"**。

***

### ⚠️ 坑4：子代理的 max\_turns 要远小于父（而且要有 early-stop 信号）

子代理跑 50 轮 = 它迷路了。给一个合理的：

| 子代理类型            | max\_turns 建议 |
| ---------------- | ------------- |
| 只读探索（explorer）   | 10–15         |
| 实现者（implementer） | 20–30         |
| 验证/review        | 8–12          |

并考虑：如果子代理连续 3 轮都在调同一个工具同样参数 → 直接 `break` 并返回 "appears stuck"。

***

### ⚠️ 坑5：（衔接第六期）子代理 vs Agent Team 的区别

第五期讲的是 **sub-agent = 主代理派生的临时工，单向汇报**。\
第六期要讲的是 **Team = 多个较对等角色协作，可能有共享黑板/消息总线/更明确的分工拓扑**。

所以第五期你只要守住一条就够了：

> **父子关系清晰：谁派活、谁交差、交差只交摘要。**

***

## 六、验收：这期学透的标志

给主 Agent 这个任务：

> *"这个仓库用了什么测试框架和断言风格？只做调查不要改任何文件，把结论告诉我。"*

你应该能在主 Agent 的行为里看到：

```
📌 assistant → tool_use: dispatch_subagent
   prompt="investigate test framework..."
📌 [SubAgent explorer] 启动 → 独立上下文 → 读 pyproject.toml / tox.ini / setup.cfg
📌 [SubAgent explorer] 返回 → "pytest, config=pyproject.toml, evidence=..."
📌 主 Agent 拿到 tool_result → 继续 / 更新 TodoWrite
```

而主 Agent 的 `messages` 里**没有** explorer 读过的一堆文件内容——只有那一句摘要。

***

如果你愿意把第五期你跟着敲的代码中 **`dispatch_subagent`** **的 handler 函数 +** **`run_subagent`** **函数 + registry 部分**贴出来（哪怕是截图表格也行），我可以帮你做一次「对齐检查」：**隔离是否真隔离了、白名单有没有漏、输出截断策略是否到位、以及它是否已经具备安全演进到第六期 Team 模式的接缝。**

## 第六期总结：Agent Team 团队协作 —— 从"派临时工"到"养一支班底"

***

### 一句话定调

> 第二期：**tool use 闭环**（能动手）\
> 第三期：**记忆系统**（不忘事）\
> 第四期：**任务规划/TodoList**（有步骤）\
> 第五期：**子代理 sub-agent**（隔离上下文，外包脏活，办完即散）\
> **第六期：子代理的致命缺陷是"办完即散"——没有身份、没有跨轮记忆、不能持续交接。Agent Team 要解决的，就是把它升级成"正式员工"。**

***

## 一、这期要解决的核心矛盾：Sub-Agent 为什么不够？

第五期的 `dispatch_subagent` 生命周期是：

```
创建独立上下文 → 执行差事 → 回传摘要 → 💀销毁
```

它完美适用于**一次性探索/调研**，但一到**长期项目协作**就露馅：

| 场景                                    | Sub-Agent 翻车点                                     |
| ------------------------------------- | ------------------------------------------------- |
| Alice 写代码 → Bob 审查 → Alice 按意见修改（第二轮） | sub-agent 每次都是全新上下文，Bob 不记得上一轮看了什么，Alice 不记得自己写过啥 |
| 需要多个角色反复交接同一个任务                       | 没有"身份"——你派出去的是匿名临时工，不是"审查员Bob"                    |
| 你想看团队里谁在忙、谁卡住了                        | 没有任何持久状态可查                                        |
| 两个角色需要互发消息（不只是向 Lead 汇报）              | sub-agent 单向汇报回 Lead，没有 peer-to-peer 通道           |

所以这期的命题是：

> **不是"再 spawn 一个 sub-agent"，而是建立：有名字的队友 + 持久生命周期 + 通信通道 + 总控调度。**

***

## 二、Agent Team 的最小组成（视频的架构骨架）

根据项目代码结构（`agent/team.py` + `agent/tools/team.py` + `.team/` 目录约定），这期搭的不是什么重量级消息队列，而是一套**够用到能跑起来的最小结构**：

### ① Lead（总控 / 包工头）

Lead **就是你原有的主 Agent**。它不变——仍然是那个跑 `agent_loop`、持有 system prompt、调工具的那个进程。但它**新增了一组 team 管理工具**：

```
send_message   → 给某个队友发任务/信息
read_inbox     → 读自己的回禀（来自队友的消息）
list_members   → 看团队花名册和状态
```

Lead 的职责永远是：**理解用户目标 → 分解 → 分配 → 汇总结果 → 解散**。

### ② Teammate（固定队友 / 有身份的持久 Agent）

每个 teammate 不是一个"函数调用"，而是一个**持久运行的小型 Agent 实例**：

- 有自己的 **`messages[]`** **历史**（跨轮记忆——这就是跟 sub-agent 最根本的区别）
- 有自己的 **`system_prompt`** **模板**（定义角色：coder / reviewer / researcher / tester…）
- 有自己的 **工具白名单**（reviewer 不需要 `write_file`，coder 需要）
- 跑在自己的 **线程 / 异步任务** 里，做完一轮不销毁，回到 idle 等下一封消息

关键：teammate 的 messages 从创建那一刻起就积累，下一次被 Lead 唤醒时**还记得上次交接到了哪**。

### ③ `.team/config.json` —— 团队花名册（Roster）

本质是一个 JSON 文件，充当"人事档案"：

```json
{
  "members": {
    "alice": {
      "role": "coder",
      "status": "idle",
      "system_prompt_path": "templates/teammates/coder.md",
      "tool_whitelist": ["read_file", "write_file", "run_command", "bash"],
      "inbox_path": ".team/inbox/alice.jsonl"
    },
    "bob": {
      "role": "reviewer",
      "status": "idle",
      "system_prompt_path": "templates/teammates/reviewer.md",
      "tool_whitelist": ["read_file", "grep", "glob"],
      "inbox_path": ".team/inbox/bob.jsonl"
    }
  }
}
```

花名册解决的是**身份问题**：不再 `run_subagent(prompt)` 匿名派遣，而是 `send_message(to="bob", content="请审查 PR diff: ...")`。

### ④ `.team/inbox/*.jsonl` —— 文件收件箱（Message Bus 最简形态）

视频里最务实的设计选择：**不用 Redis / RabbitMQ，就用文件做邮箱**。

每个 teammate 一个 inbox 文件：

```
.team/inbox/alice.jsonl
.team/inbox/bob.jsonl
.team/inbox/lead.jsonl    ← teammates 把回禀写这里
```

**发送消息 = 向目标 JSONL 追加一行**（append-only，天然并发安全）：

```python
def send_message(to: str, from_: str, content: str, task_id: str = None):
    msg = {
        "from": from_,
        "to": to,
        "ts": time.time(),
        "task_id": task_id,
        "content": content,
        "status": "unread"
    }
    inbox_path = f".team/inbox/{to}.jsonl"
    with open(inbox_path, "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
```

**读消息 = 读出所有 unread 行 → 清空/标记读**（或读完后 archive）：

```python
def read_inbox(inbox_path):
    if not os.path.exists(inbox_path):
        return []
    with open(inbox_path) as f:
        lines = f.readlines()
    # 清空（或移动到 .processed）
    open(inbox_path, "w").close()
    return [json.loads(l) for l in lines if l.strip()]
```

这就是搜索结果里那句话的意思：

> **MessageBus 的底座就是文件——发送是 append JSONL，接收是读+清空。够简单，够可靠，能跑通概念。**

***

## 三、代码层面：这期给你的新 tool 们（Lead 侧注册的团队工具）

Lead 的 `TOOLS` 列表现在追加一组 **team management tools**：

### Tool 1：`send_message`

```json
{
  "name": "send_message",
  "description": "Send a message/task to a teammate by name. The message is appended to their inbox. They will pick it up on their next cycle.",
  "input_schema": {
    "type": "object",
    "properties": {
      "to":      {"type": "string", "description": "teammate name, e.g. 'alice' or 'bob'"},
      "content": {"type": "string", "description": "the message / task description"},
      "task_id": {"type": "string", "description": "optional tag to track which task this belongs to"}
    },
    "required": ["to", "content"]
  }
}
```

Handler 做的事很简单：校验 `to` 在花名册里 → `inbox[to].append(msg)`。

### Tool 2：`read_inbox`（Lead 读自己的回禀）

```json
{
  "name": "read_inbox",
  "description": "Read messages that teammates sent back to you (lead). Returns all pending messages and clears the lead inbox.",
  "input_schema": { "type": "object", "properties": {} }
}
```

### Tool 3：`list_team`（可选但教学价值极高）

让模型能看到当前谁在线、谁 idle/working——否则它分配任务时是盲派。

***

## 四、Teammate 的生命周期（这段视频一般会演示但不强调细节）

```
Teammate 启动:
  1. 从 config.json 读取自己的角色/system_prompt/工具白名单
  2. 初始化自己的 messages = [{"role":"system","content":role_prompt}]
  3. 进入 idle loop:
     ┌─ 读自己的 inbox (.team/inbox/{name}.jsonl)
     │   ├─ 空？→ sleep(1~2s) 继续等（或等 timeout 后 idle 回报 Lead）
     │   └─ 有消息？
     │       ├─ 把消息内容 append 进自己的 messages[] 作为 user turn
     │       ├─ 跑一轮 agent_loop（受自己的工具白名单约束）
     │       ├─ 把 assistant 回复 append 进自己的 messages[]
     │       ├─ 把"回禀"写进 lead 的 inbox（send_message(to="lead", ...)）
     │       └─ 标记自己 status=idle（或=working 如果还在忙）
     └─ （可配置 auto_shutdown 空闲 N 分钟后退出）
```

**这就是"持久"二字的实体含义**：`messages[]` 不随一次派遣结束而释放，它活在 teammate 进程的整个生命周期里。

***

## 五、一个完整的演示场景（视频大概跑的这个感觉）

> **用户**："帮我实现一个 `todo-cli`，要有 add / list / done 三个命令，然后让 reviewer 审查代码质量。"

流程序列：

```
Lead 思考：
  → 调 send_message(to="alice", content="实现 todo-cli: add/list/done ...")
  → alice 的 inbox 收到消息
  → alice 进程醒来，把自己的 messages 里加一条 user 消息
  → alice 跑 agent_loop（能用 write_file / run_command）
  → alice 写完，调 send_message(to="lead", content="done. files: ...")

Lead 读 inbox → 看到 alice 完工
  → 调 send_message(to="bob", content="审查 alice 的代码，重点看 ...")
  → bob 醒来（只读工具：read_file/grep）→ 读代码
  → bob 回 lead: "LGTM / 建议改 xxx"

Lead 汇总 → 给用户最终答复
```

如果你看视频时注意看终端输出，它展示的其实就是这些 inbox 文件的读写 + Lead/teammate 两个进程交替醒来的过程。

***

## 六、这期「讲了的」vs「没讲清但要命」的点

### ✅ 讲了的

- sub-agent 的局限（办完即散）
- 需要"身份/持久/通信"三件套
- 文件 inbox 作为最简 MessageBus
- 花名册 config.json 管理成员
- Lead 通过 team tools 调度

### ⚠️ 没讲透 / 你写代码必踩的坑（重点补充）

***

#### 坑① 最核心：Teammate 到底跑在哪个线程/进程？——视频常模糊化处理

教学上最简单的两种实现：

| 方案                                                                                                          | 适合                                             |
| ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **方案 A：轮询式（最推荐起步）** —— teammate 就是个函数 `run_teammate(name, max_cycles)`，Lead 的 handler 里调它 **同步**，等它跑完一轮再收结果 | 好写、好调试、不出并发诡异 bug                              |
| **方案 B：threading + Event** —— teammate 跑后台线程，inbox 有新消息就 `event.set()` 唤醒                                   | 更像"真·常驻队友"，但你要处理线程安全（好在 inbox 是文件，append 天然安全） |

手搓阶段建议 **方案 A 先跑通**（别一上来多线程），把正确性验证完再进化。

***

#### 坑② "持久 messages"带来的窗口爆炸——第三期的记忆问题杀回来了，而且翻倍

Teammate 的 `messages[]` 也会无限增长。视频为了 demo 干净通常不演示长时运行。

你要在 teammate 的 agent\_loop 里复用第三期的 **trim/摘要逻辑**：

```python
# teammate 自己的上下文管理（跟第三期同构）
def teammate_build_context(teammate_state, new_user_msg):
    msgs = teammate_state.messages + [new_user_msg]
    return trim_to_budget(msgs, BUDGET_PER_TEAMMATE)
```

不然 teammate 跑几轮后自己就 OOM / 超窗口。

***

#### 坑③ 消息丢失 / 竞态的经典场景

如果 Lead 连续两次 `send_message(to="alice")` 而你 inbox 的读法是"读→清空"，会出现：

```
T1: Lead 写 msg1 → append
T2: Alice 读 inbox → 拿到 [msg1] → 清空文件
T3: Lead 写 msg2 → append（此时文件只有 msg2）
```

这其实没问题（msg1 已经被 alice 消费了）。但如果你 **忘了 append 用** **`'a'`** **模式**、或者中途崩溃导致行写半截——你需要知道 JSONL 的唯一脆弱点：

```python
# 加固版：每行必须是完整 JSON，写之前不 truncate
import fcntl
with open(path, "a") as f:
    fcntl.flock(f, fcntl.LOCK_EX)          # 文件锁（Linux/Mac）
    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    fcntl.flock(f, fcntl.LOCK_UN)
```

Windows 上可以用 `msvcrt.locking` 或干脆接受"教学阶段基本不会撞"的现实。

***

#### 坑④ 任务归属不明——你需要一个轻量 Task ID 绑定

否则对话会变成：

```
Lead: "bob 你说审查完了，但你审查的是哪一版的代码？"
Bob:  ...
```

补一个最小 task tracking：

```python
task = {"id": "task-003", "assignee": "alice", "desc": "...", "status": "done", "review_by": "bob"}
```

存在 `.team/tasks.jsonl`，`send_message` 时把 `task_id` 带进去，所有消息都能溯源。

***

#### 坑⑤ 什么时候该用 Team vs 什么时候 sub-agent 就够了（决策树）

视频演示的是 Team 所以必然说 Team 好，但工程上你要记住：

| 条件                  | 用 sub-agent         | 用 Team      |
| ------------------- | ------------------- | ----------- |
| 一次性调研/read-only     | ✅                   | ❌ 杀鸡用牛刀     |
| 需要 2+ 轮交接同一工件       | ❌ 失忆                | ✅           |
| 需要角色权限隔离（只读审查员）     | ⚠️ 靠 prompt 保证 = 虚的 | ✅ 代码层白名单    |
| 任务 < 5 分钟能跑完        | ✅                   | ❌ 协调开销 > 收益 |
| 多角色反复 review→rework | ❌                   | ✅           |

一句话：**Team 的成本是"维护身份+花名册+inbox+生命周期"，收益是"角色隔离+持续记忆+可审计交接"。轻量任务不值得付这个税。**

***

## 七、六期全部串起来——你学到的到底是什么

| 期      | 关键词                          | 你得到的零件                       |
| ------ | ---------------------------- | ---------------------------- |
| ① 概念   | Agent ≠ Chatbot              | 思维框架                         |
| ② 骨架   | LLM + tool\_use + while-loop | `agent_loop` 最小闭环            |
| ③ 记忆   | 短期/摘要/长期三层                   | `history` 管理 + trim + 持久化    |
| ④ 规划   | 外部化 TodoList                 | harness 层结构化状态（不只是 messages） |
| ⑤ 隔离   | sub-agent / 独立上下文外包          | `run_subagent()` 防主上下文污染     |
| ⑥ Team | 身份+生命周期+inbox                | **把上面所有零件组织成一个可扩展的系统**       |

到第六期结束时，你手里的不是"调用了工具的聊天框"，而是一个：

> **有记忆、有计划、能外包脏活、还能组建固定班底协作的本地 Agent 框架**——百行级核心，但所有关键概念都就位了。

***

