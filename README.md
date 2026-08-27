# FixTrace

> **隐私优先的软件事件调查与恢复验证。**<br>
> **Privacy-first software incident triage and recovery verification.**

FixTrace 将杂乱的 API、数据库、容器、依赖、构建、测试、部署和应用日志转换成可审计的调查记录。它会在本地脱敏敏感信息、判断事件类型、提取运行信号、生成稳定的故障指纹和场景化排查清单，并通过修复前后的输出判断系统是否真正恢复。

FixTrace turns noisy API, database, container, dependency, build, test, deployment, and application logs into an auditable investigation record. It locally redacts sensitive data, classifies the incident, extracts operational signals, creates stable failure fingerprints and scenario-specific playbooks, then compares before/after runs to decide whether recovery is proven.

**纯日志分析无需代码仓库，也不需要 AI API。**<br>
**Log-only analysis requires neither a repository nor an AI API.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)
![License](https://img.shields.io/badge/license-MIT-75f0bd)

## 为什么不只使用编程智能体？ / Why not only use a coding agent?

Codex 等编程智能体擅长交互式分析和修改代码。FixTrace 负责工作流中的另一个环节：可重复的故障接收、结构化证据和机器可检查的恢复验证。

Coding agents such as Codex excel at interactive reasoning and code changes. FixTrace handles a different part of the workflow: repeatable failure intake, structured evidence, and machine-checkable recovery verification.

| 对比维度 / Dimension | 编程智能体 / Coding agent | FixTrace |
|---|---|---|
| 工作方式 / Workflow | 交互式推理与代码修改<br>Interactive reasoning and code changes | 无人值守、确定性的日志处理<br>Unattended, deterministic log processing |
| 输出 / Output | 回答一次对话<br>Answers one conversation | 生成可移植证据和稳定指纹<br>Produces portable evidence and stable fingerprints |
| 一致性 / Consistency | 结果依赖提示词和上下文<br>Depends on prompt and context | 在脚本、支持流程和 CI 中执行相同规则<br>Applies the same rules in scripts, support workflows, and CI |
| 修复判断 / Repair decision | 可以提出合理的修复方案<br>Can propose a plausible repair | 只有前后证据满足条件才会标记为 `verified`<br>Requires before/after evidence before saying `verified` |
| 隐私 / Privacy | 可能使用托管模型<br>May use a hosted model | 核心分析完全在本地运行<br>Core analysis runs locally without sending logs to a model |

两者可以协同工作：FixTrace 准备经过脱敏的结构化证据，开发者或编程智能体负责调查和修改代码，最后由 FixTrace 充当恢复验证门禁。

They work well together: FixTrace prepares sanitized, structured evidence; a developer or coding agent investigates and changes the code; FixTrace then acts as the recovery verification gate.

## v0.3 已支持 / What works in v0.3

- 无需克隆或运行代码，直接分析粘贴的日志。<br>
  Analyze pasted logs without cloning or executing a repository.
- 识别九类软件事件：测试、构建、依赖、API/网络、数据库、容器/平台、配置、应用运行时和未知事件。<br>
  Classify nine incident domains: tests, builds, dependencies, API/network, databases, containers/platforms, configuration, application runtime, and unknown events.
- 支持 pytest、Jest/Vitest、Go test、Maven/Gradle、HTTP、数据库、容器终止、依赖解析、编译器和通用应用日志。<br>
  Detect pytest, Jest/Vitest, Go test, Maven/Gradle, HTTP, database, container, dependency, compiler, and generic application failures.
- 提取 HTTP 状态、平台原因、数据库代码、源码位置、时间戳、追踪上下文、故障数量和超时信号。<br>
  Extract HTTP statuses, platform reasons, database codes, source locations, timestamps, trace context, failure counts, and timeout signals.
- 生成严重程度和针对具体场景的首轮排查清单。<br>
  Produce a severity label and a domain-specific first-response playbook.
- 在任务存储和报告前脱敏 Token、API Key、密码、Bearer 凭据、私钥和追踪标识符。<br>
  Redact tokens, API keys, passwords, bearer credentials, private keys, and trace identifiers before task storage and reporting.
- 跨技术栈标准化故障并生成稳定的 `ft-…` 指纹。<br>
  Normalize failures across ecosystems and assign stable `ft-…` fingerprints.
- 保守地比较修复前后输出：<br>
  Compare before/after output conservatively:
  - `verified`：原始故障指纹消失，并且出现明确的成功信号。<br>
    Original fingerprints disappeared and an explicit pass signal exists.
  - `failed`：至少一个原始故障指纹仍然存在。<br>
    At least one original fingerprint remains.
  - `inconclusive`：原始故障消失，但结果不明确或出现了新故障。<br>
    The original disappeared, but the rerun is ambiguous or contains new failures.
- 可选读取本地目录或公开 GitHub 仓库，补充技术栈上下文。<br>
  Optionally inspect a local directory or public GitHub repository for stack context.
- 可选择在可信本地仓库的隔离副本中复现 pytest。<br>
  Optionally reproduce pytest in an isolated copy of a trusted local repository.
- 提供 CLI、异步 FastAPI API 和浏览器控制台。<br>
  Use the CLI, asynchronous FastAPI API, or browser dashboard.
- 导出独立 Markdown 证据报告或完整 JSON 结果。<br>
  Export a standalone Markdown evidence report or full JSON result.
- 使用 `fixtrace verify` 作为自动化门禁：退出码 `0` 表示已验证，其他结果返回 `1`。<br>
  Use `fixtrace verify` as an automation gate: exit code `0` means verified; every other result exits `1`.

FixTrace 使用确定性规则。置信度表示规则匹配强度，不代表根因已经得到证明。

FixTrace uses deterministic rules. A confidence score describes rule-match strength; it does not claim that the root cause has been proven.

## 适用人群 / Who it helps

| 用户 / User | 示例输入 / Example input | FixTrace 输出 / Output |
|---|---|---|
| 应用开发者<br>Application developer | 异常堆栈或 ERROR 日志<br>Exception or error-level log | 运行时指纹和源码优先排查清单<br>Runtime fingerprint and source-first playbook |
| QA 工程师<br>QA engineer | pytest、Jest、Go 或 Java 测试失败<br>Failed pytest, Jest, Go, or Java test | 标准化测试契约和回归证据<br>Normalized test contract and regression evidence |
| SRE / DevOps | HTTP 5xx、超时、OOMKilled、CrashLoopBackOff | 运行信号和平台排查清单<br>Operational signals and platform response checklist |
| 数据/后端工程师<br>Data / backend engineer | SQLSTATE、死锁、连接池耗尽<br>SQLSTATE, deadlock, pool exhaustion | 数据库分类和状态检查<br>Database classification and state checks |
| 技术支持<br>Technical support | 不含源码的用户侧脱敏日志<br>Sanitized customer-side log without source code | 可分享的事件调查档案<br>Shareable incident profile without cloning a repository |

FixTrace 不局限于 GitHub Actions 或 CI。代码仓库是可选项；一份故障日志就能开始调查，再提供一份修复后的日志即可进行恢复验证。

FixTrace is not limited to GitHub Actions or CI. A repository is optional; one failure log is enough to begin, and an after-fix log turns the analysis into a recovery gate.

## 快速开始 / Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn fixtrace.api.app:app --reload --port 8080
```

打开 <http://127.0.0.1:8080>，点击 **Load demo**，无需仓库即可调查一次 API 故障，并验证服务从 HTTP 503 恢复到 HTTP 200。

Open <http://127.0.0.1:8080> and choose **Load demo** to investigate a repository-free API outage and verify recovery from HTTP 503 to HTTP 200.

### 仅分析日志 / Analyze only a log

```bash
fixtrace analyze \
  --failure-file artifacts/failing-run.txt \
  --output reports/investigation.md
```

### 添加仓库上下文 / Add repository context

```bash
fixtrace analyze /path/to/repository \
  --failure-file artifacts/failing-run.txt \
  --output reports/investigation.md
```

### 验证修复 / Prove a repair

```bash
fixtrace verify \
  --before artifacts/failing-run.txt \
  --after artifacts/after-fix-run.txt \
  --output reports/verification.md
```

只有原始故障指纹消失，并且修复后输出包含可识别的成功信号时，该命令才以成功状态退出。因此它可以作为 CI 步骤或合并前质量门禁。

The command exits successfully only when the original fingerprints are absent and the after-fix output contains a recognized success signal. This makes it suitable for a CI step or pre-merge quality gate.

### 复现可信 pytest 项目 / Reproduce a trusted pytest project

```bash
fixtrace analyze examples/python_buggy --execute
```

`--execute` 是明确的信任选择。Web API 只有在同时启用 `FIXTRACE_ALLOW_LOCAL_SOURCES=1` 和 `FIXTRACE_ALLOW_LOCAL_EXECUTION=1` 后，才会接受本地路径并运行 pytest。

`--execute` is an explicit trust decision. The Web API accepts local paths and executes pytest only when both `FIXTRACE_ALLOW_LOCAL_SOURCES=1` and `FIXTRACE_ALLOW_LOCAL_EXECUTION=1` are enabled.

## 证据流水线 / Evidence pipeline

```text
intake → checkout/context → detect → reproduce/ingest → diagnose → verify → report
```

FixTrace 明确区分观察事实和推断结果：

FixTrace keeps observations separate from inferences:

- 事件档案判断运行领域并展示规则提取的信号。<br>
  Incident profiles classify the operational domain and expose rule-derived signals.
- 首轮排查清单由事件类型选择，而不是由不透明的对话生成。<br>
  First-response playbooks are selected by incident type instead of generated from an opaque chat.
- 故障记录包含标准化事实和稳定指纹。<br>
  Failure records contain normalized facts and a stable fingerprint.
- 证据账本记录每项事实的来源。<br>
  The evidence ledger records where each fact came from.
- 根因假设引用证据 ID，不会悄悄变成事实。<br>
  Root-cause hypotheses cite evidence IDs and never silently become facts.
- 恢复验证比较前后指纹，并要求明确的成功信号。<br>
  Recovery verification compares before/after fingerprints and requires an explicit success signal.

疑似敏感值会在解析和报告前替换为 `[REDACTED]`。内置脱敏器采取保守规则，不能替代专业的密钥扫描工具。

Likely sensitive values are replaced with `[REDACTED]` before parsing and reporting. The built-in redactor is conservative and is not a substitute for a dedicated secret scanner.

## API

| 方法 / Method | 端点 / Endpoint | 用途 / Purpose |
|---|---|---|
| `GET` | `/api/health` | 服务能力和执行策略<br>Capabilities and execution policy |
| `POST` | `/api/analyses` | 创建日志分析或仓库调查任务<br>Queue a log analysis or repository investigation |
| `GET` | `/api/analyses` | 列出调查任务<br>List investigations |
| `GET` | `/api/analyses/{id}` | 查询任务状态和结构化结果<br>Poll task state and structured results |
| `GET` | `/api/analyses/{id}/report` | 下载 Markdown 报告<br>Download the Markdown report |

无需仓库的 API 事件恢复验证请求 / Repository-free API recovery verification request:

```json
{
  "repository": null,
  "execution_mode": "inspect",
  "failure_output": "GET /api/checkout\nHTTP/1.1 503 Service Unavailable\ntimeout after 5s",
  "verification_output": "GET /api/checkout\nHTTP/1.1 200 OK\nhealth check passed"
}
```

## 安全模型 / Security model

仓库测试属于可执行代码，因此 FixTrace 默认采用保守策略：

Repository tests are executable code, so FixTrace uses conservative defaults:

- 纯日志分析不会执行仓库代码。<br>
  Log-only analysis does not execute repository code.
- Web 请求默认不能访问服务器本地路径或运行测试。<br>
  Web requests cannot access server-local paths or execute tests by default.
- GitHub 来源必须符合 `https://github.com/owner/repository`。<br>
  GitHub sources must match `https://github.com/owner/repository`.
- 本地执行在仓库副本中进行，并使用不包含主机 API Key 或 Token 的最小环境。<br>
  Local execution uses a copied workspace and a minimal environment without host API keys or tokens.
- 用户不能自定义执行命令；本地执行目前只调用检测到的 pytest。<br>
  Command selection is not user-controlled; local execution currently invokes detected pytest.
- 输出有大小限制，执行有超时限制。<br>
  Output is size-capped and execution has a timeout.
- 常见凭据和追踪标识符会在进入结果前被脱敏。<br>
  Common credentials and trace identifiers are redacted before entering results.

本地执行并非完整沙箱，可能仍有网络访问。只应对可信代码使用；不可信仓库应在一次性虚拟机中运行。详情见 [SECURITY.md](SECURITY.md)。

Local execution is not a complete sandbox and may retain network access. Use it only for trusted code; run untrusted repositories in a disposable VM. See [SECURITY.md](SECURITY.md).

## Docker

```bash
docker compose up --build
```

提供的容器使用只读文件系统、禁止权限提升，并关闭本地来源和测试执行。它支持安全的纯日志分析和公开仓库检查。

The supplied container is read-only, drops privilege escalation, and disables local sources and test execution. It supports safe log-only analysis and public repository inspection.

## 开发 / Development

```bash
pip install -e '.[dev]'
ruff check src tests
pytest
```

`examples/python_buggy` 中包含一个故意损坏的项目，它不会进入 FixTrace 自身测试，仅用于演示故障复现。

The deliberately broken project in `examples/python_buggy` is excluded from FixTrace's own test suite and exists only to demonstrate failure reproduction.

## 路线图 / Roadmap

- 持久化故障指纹历史和重复事件趋势。<br>
  Persistent fingerprint history and recurring-incident trends.
- 自动接入 GitHub Actions 日志和构建产物。<br>
  GitHub Actions log and artifact ingestion.
- 容器化、禁用网络的复现工作节点。<br>
  Containerized, network-disabled reproduction workers.
- SARIF 和 GitHub Check 输出。<br>
  SARIF and GitHub Check output.
- 增加云服务、消息队列、缓存和数据流水线适配器。<br>
  More adapters for cloud providers, queues, caches, and data pipelines.
- 可选的 AI 增强，但只能引用已经收集的证据。<br>
  Optional AI enrichment that can only cite collected evidence.

## 许可证 / License

MIT，详见 [LICENSE](LICENSE)。<br>
MIT. See [LICENSE](LICENSE).
