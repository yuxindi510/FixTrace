"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fixtrace.core.models import AnalysisRequest, ExecutionMode
from fixtrace.core.pipeline import AnalysisPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fixtrace",
        description="Inspect or reproduce pytest failures and produce an evidence report.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="Analyze a local or public GitHub repository")
    analyze.add_argument("repository", help="Local directory or public GitHub URL")
    analyze.add_argument("--failure-file", type=Path, help="Text file containing pytest/CI output")
    analyze.add_argument(
        "--execute",
        action="store_true",
        help="Execute pytest locally in a copied workspace; use only for trusted repositories",
    )
    analyze.add_argument("--json", action="store_true", help="Print the full JSON result")
    analyze.add_argument("--output", type=Path, help="Write the Markdown report to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "analyze":
        return 2

    failure_output = ""
    if args.failure_file:
        failure_output = args.failure_file.read_text(encoding="utf-8", errors="replace")
    mode = ExecutionMode.LOCAL if args.execute else ExecutionMode.INSPECT
    request = AnalysisRequest(
        repository=args.repository,
        failure_output=failure_output,
        execution_mode=mode,
    )
    pipeline = AnalysisPipeline(
        allow_local_execution=args.execute,
        allow_local_sources=True,
    )
    try:
        report = pipeline.run(request)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"fixtrace: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.markdown, encoding="utf-8")
    print(report.model_dump_json(indent=2) if args.json else report.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
