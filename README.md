# FixTrace

> **会主动查证据、读源码，并用真实结果验证修复的软件故障调查 Agent。**<br>
> **A software incident investigation agent that gathers evidence, inspects source, and verifies recovery with real results.**

FixTrace 面向测试、API、数据库、容器、依赖、构建、部署和应用运行时故障。LLM 在有边界的循环中规划下一步并调用只读工具；确定性引擎负责日志解析、本地脱敏、稳定指纹和修复前后验证。最终结论必须引用证据 ID 或工具观察 ID，模型不能自行把修复标记为成功。

FixTrace investigates failures across tests, APIs, databases, containers, dependencies, builds, deployments, and application runtimes. An LLM plans each next step and calls bounded read-only tools, while deterministic components handle parsing, local redaction, stable fingerprints, and before/after verification. Every agent finding must cite an evidence or observation ID, and the model cannot declare a repair verified by itself.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)
![License](https://img.shields.io/badge/license-MIT-75f0bd)

## 为什么它不等于“直接使用 Codex”？ / Why not just use Codex?

Codex 是通用编程智能体，适合在一个开发会话中理解、修改和运行代码。FixTrace 是可以嵌入支持平台、值班流程、内部工具和自动化任务的专用故障调查 Agent。

Codex is a general coding agent for understanding, changing, and running code in a development session. FixTrace is a specialized incident agent designed to sit inside support platforms, on-call workflows, internal tools, and unattended jobs.

| 对比维度 / Dimension | 通用编程智能体 / General coding agent | FixTrace |
|---|---|---|
| 目标 / Purpose | 开放式软件开发任务<br>Open-ended software work | 可重复的软件故障调查<br>Repeatable software incident investigation |
| Agent 循环 / Agent loop | 工具和流程随会话变化<br>Tools and flow vary by session | 固定的观察→规划→工具→观察闭环<br>Bounded observe→plan→tool→observe loop |
| 工具权限 / Tool authority | 可修改代码并执行命令<br>May edit code and execute commands | 默认只有证据、列文件、搜源码、读源码四类只读工具<br>Four read-only tools by default: evidence, list, search, read |
| 可追溯性 / Traceability | 以对话记录为主<br>Primarily conversational history | 每个结论必须引用 `ev-*` / `obs-*`<br>Every finding must cite `ev-*` / `obs-*` |
| 隐私边界 / Privacy boundary | 取决于会话与配置<br>Depends on session and configuration | 日志和工具输出先本地脱敏，再发给模型<br>Logs and tool outputs are locally redacted before model calls |
| 修复判断 / Recovery decision | 模型可以给出判断<br>The model may offer a judgment | 只有确定性前后指纹检查能输出 `verified`<br>Only deterministic before/after checks can output `verified` |
| 集成方式 / Integration | 交互式开发界面<br>Interactive development interface | CLI、异步 API、Web 控制台、Markdown/JSON 报告<br>CLI, async API, Web UI, Markdown/JSON reports |

FixTrace 的优势不是比通用 Agent “更聪明”，而是把故障调查做成可复用、可审计、权限受限、结果可验证的产品流程。

FixTrace does not try to be “smarter” than a general agent. Its advantage is turning incident investigation into a reusable, auditable, least-authority, independently verifiable product workflow.

## v0.4 Agent 架构 / v0.4 agent architecture

```text
日志 / 仓库
Logs / repository
       │
       ▼
确定性证据层：解析 · 分类 · 脱敏 · 指纹
Deterministic evidence: parse · classify · redact · fingerprint
       │
       ▼
LLM Agent：观察 → 规划 → 只读工具 → 新观察 → 收敛
LLM Agent: observe → plan → read-only tool → observe → finalize
       │
       ▼
证据化结论：每条 Finding 引用 ev-* / obs-*
Grounded findings: every finding cites ev-* / obs-*
       │
       ▼
确定性验证：比较修复前后指纹和成功信号
Deterministic verification: compare fingerprints and pass signals
```

Agent 当前可以主动选择：

The agent can currently choose among:

- `inspect_evidence`：读取结构化证据账本。<br>
  Read the structured evidence ledger.
- `list_files`：在已准备的仓库中列出有限数量文件。<br>
  List a bounded set of files in the prepared repository.
- `search_source`：进行大小受限的源码文本搜索。<br>
  Run a size-bounded literal source search.
- `read_source`：读取仓库内有限行数，路径穿越和符号链接逃逸会被拒绝。<br>
  Read a bounded line range; path traversal and symlink escape are rejected.
- `finalize`：提交带有效证据引用的结论；无效引用会被退回修正。<br>
  Submit findings with valid citations; invalid citations are rejected for correction.

Agent 没有 Shell、写文件、网络请求或代码修改工具。最大步数默认为 6，避免失控循环和不可预测费用。报告只记录简短的动作理由、参数和观察，不保存模型的私有思维链。

The agent has no shell, write, network, or code-editing tool. It stops after six model calls by default to prevent runaway loops and unpredictable cost. Reports retain concise action reasons, arguments, and observations—not private chain-of-thought.

## 支持范围 / Coverage

- 九类事件：测试、构建、依赖、API/网络、数据库、容器/平台、配置、应用运行时和未知事件。<br>
  Nine domains: test, build, dependency, API/network, database, container/platform, configuration, application/runtime, and unknown incidents.
- pytest、Jest/Vitest、Go test、Maven/Gradle、HTTP、数据库、容器终止、依赖解析、编译器和通用应用日志。<br>
  pytest, Jest/Vitest, Go test, Maven/Gradle, HTTP, database, container, dependency, compiler, and generic application logs.
- 纯日志、公开 GitHub 仓库或可信本地目录。<br>
  Log-only input, public GitHub repositories, or trusted local directories.
- HTTP 状态、平台原因、数据库代码、源码位置、时间戳、追踪上下文、故障数量和超时等信号。<br>
  HTTP status, platform reason, database code, source location, timestamp, trace context, failure count, timeout, and related signals.
- 修复结果分为 `verified`、`failed`、`inconclusive` 和 `pending`。<br>
  Recovery results are `verified`, `failed`, `inconclusive`, or `pending`.

FixTrace 不局限于 CI。开发、测试、SRE、技术支持、内部平台和任何能提供故障日志的团队都可以使用。

FixTrace is not limited to CI. It works for developers, QA, SRE, support, internal platforms, and any team that can supply failure evidence.

## 快速开始 / Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### 1. 配置 LLM / Configure the LLM

FixTrace v0.4 内置 OpenAI Responses API Provider。API Key 只从服务端环境变量读取，永远不通过分析请求提交。模型 ID 要显式配置，避免项目悄悄切换模型或产生意外费用。

FixTrace v0.4 includes an OpenAI Responses API provider. The API key is read only from the server environment and is never accepted in an analysis request. The model ID is explicit so the project never silently changes models or cost.

```bash
export FIXTRACE_LLM_PROVIDER=openai
export FIXTRACE_LLM_MODEL=<your-model-id>
export OPENAI_API_KEY=<your-api-key>
```

可选配置 / Optional settings:

```bash
export FIXTRACE_LLM_BASE_URL=https://api.openai.com/v1
export FIXTRACE_LLM_TIMEOUT_SECONDS=60
export FIXTRACE_AGENT_MAX_STEPS=6
export FIXTRACE_AGENT_MAX_TOOL_OUTPUT_CHARS=12000
```

实现使用 `POST /v1/responses`、关闭响应存储，并由 FixTrace 在本地执行自定义只读工具。接口详情见 [OpenAI Responses API 官方文档](https://developers.openai.com/api/reference/resources/responses/methods/create)。

The implementation uses `POST /v1/responses`, disables response storage, and executes FixTrace's custom read-only tools locally. See the [official OpenAI Responses API documentation](https://developers.openai.com/api/reference/resources/responses/methods/create).

### 2. 启动 Web 应用 / Start the Web app

```bash
uvicorn fixtrace.api.app:app --reload --port 8080
```

打开 <http://127.0.0.1:8080>。页面状态栏会显示 Agent 是否配置完成。

Open <http://127.0.0.1:8080>. The status line shows whether an agent provider is configured.

### 3. 调查故障 / Investigate a failure

```bash
fixtrace analyze /path/to/repository \
  --failure-file artifacts/failing-run.txt \
  --output reports/investigation.md
```

默认 `auto` 模式在 LLM 已配置时运行 Agent；未配置时仍返回确定性证据报告。

The default `auto` mode runs the agent when an LLM is configured and falls back to the deterministic evidence report otherwise.

```bash
# Agent 未完成则命令失败 / Fail unless the agent completes
fixtrace analyze /path/to/repository \
  --failure-file artifacts/failing-run.txt \
  --require-agent

# 明确跳过 LLM / Explicitly skip the LLM
fixtrace analyze \
  --failure-file artifacts/failing-run.txt \
  --no-agent
```

### 4. 独立验证修复 / Verify recovery independently

```bash
fixtrace verify \
  --before artifacts/failing-run.txt \
  --after artifacts/after-fix-run.txt \
  --output reports/verification.md
```

`fixtrace verify` 是不调用 LLM 的机器门禁。只有原始故障指纹消失且出现明确成功信号时退出码才为 `0`。

`fixtrace verify` is a model-free machine gate. It exits `0` only when the original fingerprints disappear and an explicit pass signal is present.

### 可信本地复现 / Trusted local reproduction

```bash
fixtrace analyze examples/python_buggy --execute --require-agent
```

`--execute` 会在仓库副本中运行检测到的 pytest，仅应用于可信代码。Web 服务还要求 `FIXTRACE_ALLOW_LOCAL_SOURCES=1` 和 `FIXTRACE_ALLOW_LOCAL_EXECUTION=1`。

`--execute` runs detected pytest in a repository copy and is for trusted code only. The Web service additionally requires `FIXTRACE_ALLOW_LOCAL_SOURCES=1` and `FIXTRACE_ALLOW_LOCAL_EXECUTION=1`.

## API

| 方法 / Method | 端点 / Endpoint | 用途 / Purpose |
|---|---|---|
| `GET` | `/api/health` | Agent 配置、能力和执行策略<br>Agent configuration, capabilities, and execution policy |
| `POST` | `/api/analyses` | 创建调查任务<br>Queue an investigation |
| `GET` | `/api/analyses` | 列出调查任务<br>List investigations |
| `GET` | `/api/analyses/{id}` | 查询阶段、Agent Trace 和结果<br>Poll stages, agent trace, and results |
| `GET` | `/api/analyses/{id}/report` | 下载 Markdown 报告<br>Download the Markdown report |

```json
{
  "repository": "https://github.com/owner/repository",
  "execution_mode": "inspect",
  "agent_mode": "auto",
  "failure_output": "GET /api/checkout\nHTTP/1.1 503 Service Unavailable",
  "verification_output": "GET /api/checkout\nHTTP/1.1 200 OK\nhealth check passed"
}
```

`agent_mode` 支持：

`agent_mode` accepts:

- `auto`：配置完成则运行，否则回退到确定性报告。<br>
  Run when configured; otherwise return the deterministic report.
- `required`：Agent 未配置、调用失败、超出步数或无法形成有效引用时，任务失败。<br>
  Fail if unconfigured, unavailable, over budget, or unable to produce valid citations.
- `off`：不调用模型。<br>
  Do not call a model.

## 安全与隐私 / Security and privacy

- 日志在进入任务存储和模型上下文前，本地脱敏常见 Token、API Key、密码、Bearer 凭据、私钥和追踪标识符。<br>
  Common tokens, API keys, passwords, bearer credentials, private keys, and trace identifiers are locally redacted before task storage or model context.
- 读取源码和搜索源码的输出也会再次脱敏。<br>
  Source reads and search results receive another redaction pass.
- 模型凭据只存在于服务器环境中，不属于请求模型或报告。<br>
  Provider credentials exist only in the server environment, never in request models or reports.
- Agent 工具只读、路径受限、输出受限、步数受限。<br>
  Agent tools are read-only, path-contained, output-capped, and step-capped.
- 日志和源码仍可能包含内置规则无法识别的敏感业务数据。使用托管模型前请审查数据策略。<br>
  Logs and source may still contain sensitive business data not recognized by built-in rules. Review your data policy before using a hosted model.
- 本地执行不是完整操作系统沙箱；不可信代码应放在一次性虚拟机中。<br>
  Local execution is not a complete OS sandbox; use a disposable VM for untrusted code.

详见 [SECURITY.md](SECURITY.md)。

See [SECURITY.md](SECURITY.md).

## Docker

```bash
docker compose up --build
```

Compose 会从宿主机传入可选的 LLM 配置；未配置时容器仍能提供确定性报告。容器默认只读、禁止权限提升，并关闭本地来源和测试执行。

Compose forwards optional LLM settings from the host. Without them, the container still returns deterministic reports. The container is read-only, drops privilege escalation, and disables local sources and test execution by default.

## 开发 / Development

```bash
pip install -e '.[dev]'
ruff check src tests
pytest
```

测试使用脚本化 Fake Provider，不会访问网络或消耗模型额度。

Tests use a scripted fake provider; they make no network calls and consume no model quota.

## 路线图 / Roadmap

- 增加本地模型和其他 Provider 适配器。<br>
  Add local-model and additional provider adapters.
- 允许管理员注册经过权限声明的 MCP 只读工具。<br>
  Let administrators register permission-declared, read-only MCP tools.
- 持久化故障指纹历史、Agent 评价和回归样例。<br>
  Persist fingerprint history, agent feedback, and regression cases.
- 增加云服务、消息队列、缓存和数据流水线适配器。<br>
  Add adapters for cloud providers, queues, caches, and data pipelines.
- 输出 SARIF、GitHub Check 和可嵌入 Widget。<br>
  Export SARIF, GitHub Checks, and embeddable widgets.

## 许可证 / License

MIT，详见 [LICENSE](LICENSE)。<br>
MIT. See [LICENSE](LICENSE).
