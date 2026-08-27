# FixTrace

**Privacy-first software incident triage and recovery verification.**

FixTrace turns noisy API, database, container, dependency, build, test, deployment, and application
logs into a deterministic investigation record. It redacts likely secrets, classifies the incident,
extracts operational signals, creates stable failure fingerprints, builds a scenario-specific
first-response playbook, and compares before/after runs to decide whether recovery is proven.

No repository or AI API is required for log-only analysis.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)
![License](https://img.shields.io/badge/license-MIT-75f0bd)

## Why use this instead of only asking a coding agent?

Coding agents such as Codex are excellent interactive problem solvers. FixTrace handles a
different part of the workflow: repeatable failure intake and machine-checkable verification.

| Coding agent | FixTrace |
|---|---|
| Interactive reasoning and code changes | Unattended, deterministic log processing |
| Answers one conversation | Produces portable evidence and stable fingerprints |
| Context depends on the prompt | Applies the same rules in scripts, support workflows, and CI |
| Can propose a plausible repair | Requires before/after evidence before saying “verified” |
| May use a hosted model | Core analysis runs locally without sending logs to a model |

They work well together: FixTrace prepares sanitized, structured evidence; a developer or coding
agent investigates and changes the code; FixTrace then acts as the verification gate.

## What works in v0.3

- Analyze a pasted log without cloning or executing a repository.
- Classify nine incident domains: tests, builds, dependencies, API/network, databases,
  containers/platforms, configuration, application runtime, and unknown events.
- Detect pytest, Jest/Vitest, Go test, Maven/Gradle, HTTP failures, database errors, container
  termination reasons, dependency resolution errors, compilers, and generic application logs.
- Extract HTTP statuses, platform reasons, database codes, source locations, timestamps, trace
  context, failure counts, and timeout signals without exposing trace identifier values.
- Produce a severity label and a domain-specific first-response playbook.
- Redact common tokens, API keys, passwords, bearer credentials, private keys, and trace identifiers
  before task storage and reporting.
- Normalize failures across ecosystems and assign stable `ft-…` fingerprints.
- Compare before/after output conservatively:
  - `verified`: original fingerprints disappeared and an explicit pass signal exists;
  - `failed`: an original fingerprint remains;
  - `inconclusive`: the original disappeared but the rerun is ambiguous or has new failures.
- Inspect a local directory or public GitHub repository for additional stack context.
- Opt in to pytest reproduction in an isolated copy of a trusted local repository.
- Use the CLI, asynchronous FastAPI API, or browser dashboard.
- Export a standalone Markdown evidence report or full JSON result.
- Use `fixtrace verify` as a CI gate: exit code `0` means verified; any other result exits `1`.

FixTrace uses deterministic rules. A confidence score describes the strength of a rule match; it
is not a claim that the root cause has been proven.

## Who it helps

| User | Example input | FixTrace output |
|---|---|---|
| Application developer | Exception or error-level application log | Runtime fingerprint and source-first playbook |
| QA engineer | Failed pytest, Jest, Go, or Java test | Normalized test contract and regression evidence |
| SRE / DevOps | HTTP 5xx, timeout, OOMKilled, CrashLoopBackOff | Operational signals and platform response checklist |
| Data / backend engineer | SQLSTATE, deadlock, pool exhaustion | Database classification and state checks |
| Technical support | Sanitized customer-side log without source code | Shareable incident profile without cloning a repository |

FixTrace is not limited to GitHub Actions or CI. A repository is optional; the smallest useful
input is one failure log, and an after-fix log turns the same analysis into a recovery gate.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn fixtrace.api.app:app --reload --port 8080
```

Open <http://127.0.0.1:8080> and choose **Load demo** to investigate a repository-free API outage
and verify its recovery from HTTP 503 to HTTP 200.

### Analyze only a log

```bash
fixtrace analyze \
  --failure-file artifacts/failing-run.txt \
  --output reports/investigation.md
```

### Add repository context

```bash
fixtrace analyze /path/to/repository \
  --failure-file artifacts/failing-run.txt \
  --output reports/investigation.md
```

### Prove a repair

```bash
fixtrace verify \
  --before artifacts/failing-run.txt \
  --after artifacts/after-fix-run.txt \
  --output reports/verification.md
```

The command exits successfully only when the original failure fingerprints are absent and the
after-fix output contains a recognized success signal. This makes it suitable for a CI step or a
pre-merge quality gate.

### Reproduce trusted pytest projects

```bash
fixtrace analyze examples/python_buggy --execute
```

`--execute` is an explicit trust decision. The Web API requires both
`FIXTRACE_ALLOW_LOCAL_SOURCES=1` and `FIXTRACE_ALLOW_LOCAL_EXECUTION=1` before it accepts local
paths and executes pytest.

## The evidence pipeline

```text
intake → checkout/context → detect → reproduce/ingest → diagnose → verify → report
```

The important product boundary is between observation and inference:

- incident profiles classify the operational domain and expose the rule-derived signals;
- first-response playbooks are selected by incident type instead of generated from an opaque chat;
- failures contain normalized facts and a stable fingerprint;
- evidence records where each fact came from;
- hypotheses cite evidence IDs and never silently become facts;
- verification compares before/after fingerprints and requires an explicit pass signal.

Likely credentials are replaced with `[REDACTED]` before parsing and reporting. The built-in
redactor is intentionally conservative and is not a substitute for a dedicated secret scanner.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Capabilities and execution policy |
| `POST` | `/api/analyses` | Queue a log analysis or repository investigation |
| `GET` | `/api/analyses` | List investigations |
| `GET` | `/api/analyses/{id}` | Poll task state and structured results |
| `GET` | `/api/analyses/{id}/report` | Download the Markdown report |

Repository-free API incident verification request:

```json
{
  "repository": null,
  "execution_mode": "inspect",
  "failure_output": "GET /api/checkout\nHTTP/1.1 503 Service Unavailable\ntimeout after 5s",
  "verification_output": "GET /api/checkout\nHTTP/1.1 200 OK\nhealth check passed"
}
```

## Security model

Repository tests execute repository code, so FixTrace uses conservative defaults:

- Log-only analysis does not execute repository code.
- Web requests cannot access server-local paths or execute tests by default.
- GitHub sources must match `https://github.com/owner/repository`.
- Local execution works on a copied workspace and receives a minimal environment without host API
  keys or tokens.
- Command selection is not user-controlled; local execution currently invokes detected pytest.
- Output is size-capped and execution has a timeout.
- Common credential forms are redacted before results enter a report.

Local execution is not a complete sandbox and may have network access. Only use it for code you
trust. Run untrusted repositories in a disposable VM. See [SECURITY.md](SECURITY.md).

## Docker

```bash
docker compose up --build
```

The supplied container is read-only, drops privilege escalation, and disables local sources and
test execution. It supports safe log-only analysis and public repository inspection.

## Development

```bash
pip install -e '.[dev]'
ruff check src tests
pytest
```

The deliberately broken project in `examples/python_buggy` is excluded from FixTrace's own test
suite and exists only to demonstrate failure reproduction.

## Roadmap

- Persistent fingerprint history and recurring-incident trends.
- GitHub Actions log and artifact ingestion.
- Containerized, network-disabled reproduction workers.
- SARIF and GitHub Check output.
- More adapters for cloud providers, queues, caches, and data pipelines.
- Optional AI enrichment that can only cite collected evidence.

## License

MIT. See [LICENSE](LICENSE).
