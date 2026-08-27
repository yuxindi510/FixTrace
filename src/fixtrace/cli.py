"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fixtrace.core.models import AgentMode, AnalysisRequest, ExecutionMode, VerificationStatus
from fixtrace.core.pipeline import AnalysisPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fixtrace",
        description="Triage software incidents and prove recovery from before/after evidence.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="Analyze a failure log and optional repository")
    analyze.add_argument(
        "repository",
        nargs="?",
        help="Optional local directory or public GitHub URL",
    )
    analyze.add_argument(
        "--failure-file",
        type=Path,
        help="Test, build, deploy, or runtime failure output",
    )
    analyze.add_argument(
        "--verification-file",
        type=Path,
        help="Optional after-fix rerun output",
    )
    analyze.add_argument(
        "--execute",
        action="store_true",
        help="Execute pytest locally in a copied workspace; use only for trusted repositories",
    )
    agent_policy = analyze.add_mutually_exclusive_group()
    agent_policy.add_argument(
        "--no-agent",
        action="store_true",
        help="Skip LLM investigation and return only deterministic evidence",
    )
    agent_policy.add_argument(
        "--require-agent",
        action="store_true",
        help="Fail unless the configured LLM agent reaches an evidence-cited conclusion",
    )
    analyze.add_argument("--json", action="store_true", help="Print the full JSON result")
    analyze.add_argument("--output", type=Path, help="Write the Markdown report to this path")

    verify = subparsers.add_parser(
        "verify",
        help="Compare before/after logs and exit successfully only when the repair is proven",
    )
    verify.add_argument("--before", type=Path, required=True, help="Before-fix failure output")
    verify.add_argument("--after", type=Path, required=True, help="After-fix rerun output")
    verify.add_argument("--json", action="store_true", help="Print the full JSON result")
    verify.add_argument("--output", type=Path, help="Write the Markdown report to this path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "analyze":
            failure_output = _read(args.failure_file)
            verification_output = _read(args.verification_file)
            mode = ExecutionMode.LOCAL if args.execute else ExecutionMode.INSPECT
            agent_mode = (
                AgentMode.REQUIRED
                if args.require_agent
                else AgentMode.OFF
                if args.no_agent
                else AgentMode.AUTO
            )
            request = AnalysisRequest(
                repository=args.repository,
                failure_output=failure_output,
                verification_output=verification_output,
                execution_mode=mode,
                agent_mode=agent_mode,
            )
            allow_execution = args.execute
        else:
            request = AnalysisRequest(
                failure_output=_read(args.before),
                verification_output=_read(args.after),
                agent_mode=AgentMode.OFF,
            )
            allow_execution = False
        pipeline = AnalysisPipeline(
            allow_local_execution=allow_execution,
            allow_local_sources=True,
        )
        report = pipeline.run(request)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"fixtrace: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.markdown, encoding="utf-8")
    print(report.model_dump_json(indent=2) if args.json else report.markdown)
    if args.command == "verify":
        return 0 if report.verification.status == VerificationStatus.VERIFIED else 1
    return 0


def _read(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
