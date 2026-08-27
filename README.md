# FixTrace

**Evidence-driven CI failure reproduction and verified repair reports.**

FixTrace turns a failed test run into a structured investigation: repository intake, stack
detection, safe-by-default reproduction, normalized failures, an evidence ledger, root-cause
hypotheses, and a portable Markdown report.

It is deliberately different from a general coding agent. The MVP does not claim a repair is
correct because a model produced a patch; it records what failed, what evidence supports each
hypothesis, and what still needs to pass before a repair is verified.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)
![License](https://img.shields.io/badge/license-MIT-75f0bd)

## What works in v0.1

- Inspect an existing pytest/CI failure without executing repository code.
- Accept an existing local directory or a public GitHub HTTPS URL.
- Detect languages, manifests, frameworks, and the supported test runner.
- Parse pytest summaries, exceptions, and source locations.
- Build evidence-linked, confidence-scored root-cause hypotheses.
- Opt in to pytest reproduction in an isolated copy of a trusted local repository.
- Use the CLI or asynchronous FastAPI dashboard.
- Export a standalone Markdown investigation report.

Patch generation and before/after patch verification are intentionally marked as pending in v0.1.
They are the next product milestone, not a result the application fabricates.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn fixtrace.api.app:app --reload --port 8080
```

Open <http://127.0.0.1:8080>.

Inspect previously captured CI output:

```bash
fixtrace analyze /path/to/repository \
  --failure-file /path/to/pytest-output.txt \
  --output reports/investigation.md
```

Reproduce tests for a repository you trust:

```bash
fixtrace analyze examples/python_buggy --execute
```

The CLI's `--execute` flag is an explicit trust decision. The Web API requires both
`FIXTRACE_ALLOW_LOCAL_SOURCES=1` and `FIXTRACE_ALLOW_LOCAL_EXECUTION=1` before it accepts local
paths and executes pytest.

## Docker

```bash
docker compose up --build
```

The supplied container is read-only, drops privilege escalation, and disables local sources and
test execution. It can inspect supplied CI output for public GitHub repositories. A dedicated
network-isolated runner image is planned before Web-triggered execution is recommended.

## Analysis pipeline

```text
intake → checkout → detect → reproduce → diagnose → verify → report
```

Each stage emits a timestamped event. Hypotheses reference evidence IDs so reviewers can separate
observations from inference.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Service capabilities and execution policy |
| `POST` | `/api/analyses` | Queue an investigation |
| `GET` | `/api/analyses` | List investigations |
| `GET` | `/api/analyses/{id}` | Poll task state and results |
| `GET` | `/api/analyses/{id}/report` | Download the Markdown report |

Example request:

```json
{
  "repository": "https://github.com/owner/repository",
  "execution_mode": "inspect",
  "failure_output": "FAILED tests/test_total.py::test_discount - AssertionError: assert 12 == 10"
}
```

## Security model

Repository tests execute repository code. FixTrace therefore uses these defaults:

- Web requests cannot access server-local paths.
- Web requests cannot execute tests.
- GitHub sources must match `https://github.com/owner/repository`.
- Local execution works on a copied workspace and receives a minimal environment without host API
  keys or tokens.
- Command selection is not user-controlled; v0.1 only invokes detected pytest.
- Output is size-capped and execution has a timeout.

Local execution is still not a complete sandbox and may have network access. Only use it for code
you trust. Run untrusted repositories in a disposable VM until the container runner milestone is
complete. See [SECURITY.md](SECURITY.md).

## Development

```bash
pip install -e '.[dev]'
ruff check src tests
pytest
```

The deliberately broken project in `examples/python_buggy` is excluded from the repository's own
test suite and exists only to demonstrate failure reproduction.

## Roadmap

- Containerized, network-disabled test runners.
- GitHub Actions workflow-log and artifact ingestion.
- Candidate patch input and before/after worktree verification.
- Python dependency environment reconstruction.
- JavaScript, Go, and Java test adapters.
- SARIF and GitHub Check output.
- Optional LLM hypothesis enrichment with strict evidence citations.
- SQLite persistence and task resumption.

## License

MIT. See [LICENSE](LICENSE).

