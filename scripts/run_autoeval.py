"""Chay AutoEval end-to-end qua run_request va xuat 5 chi so.

Cach chay:
    python scripts/run_autoeval.py --eval-set tests/eval_set/cases_c.jsonl
    python scripts/run_autoeval.py --eval-set tests/eval_set --llm stub --repeat 3

Xuat reports/autoeval_<timestamp>.json va .md, kem dataset_version de so lieu
trong bao cao truy nguoc duoc ve dung mot ban du lieu (architecture.md muc 4.4).
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.scoring import METRIC_NAMES, aggregate, grade_case  # noqa: E402

VERSION_PATH = ROOT / "src" / "tools" / "mock_data" / "VERSION"
REPORT_DIR = ROOT / "reports"


def load_cases(target: Path) -> list[dict]:
    paths = sorted(target.glob("cases*.jsonl")) if target.is_dir() else [target]
    cases = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = json.loads(line)
                if "oracle" in case:  # bo qua file case cu chua co oracle
                    cases.append(case)
    return cases


def run_one(case: dict) -> dict:
    from src.graph import run_request

    final = {}
    session_id = None
    for turn in case["turns"]:
        final = run_request(turn, session_id=session_id, _inject=case.get("inject"))
        session_id = final.get("session_id") or session_id
    return final


def dataset_version() -> str:
    try:
        return VERSION_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def to_markdown(report: dict) -> str:
    lines = [
        "# Bao cao AutoEval",
        "",
        f"- Thoi diem: {report['generated_at']}",
        f"- dataset_version: {report['dataset_version']}",
        f"- So case: {report['total_cases']}  |  So lan lap: {report['repeat']}",
        f"- LLM: {report['llm_mode']}",
        "",
        "## Chi so",
        "",
        "| Chi so | Gia tri |",
        "|---|---|",
    ]
    for name in METRIC_NAMES:
        value = report["metrics"][name]
        lines.append(f"| {name} | {'khong do duoc' if value is None else value} |")
    lines += [
        f"| avg_llm_calls | {report['avg_llm_calls']} |",
        f"| latency_p50_ms | {report['latency_p50_ms']} |",
        f"| latency_p95_ms | {report['latency_p95_ms']} |",
        "",
        "## Case truot",
        "",
    ]
    if not report["failed_cases"]:
        lines.append("Khong co case nao truot.")
    for item in report["failed_cases"]:
        lines.append(f"- **{item['id']}** ({item['category']}): {'; '.join(item['failures'])}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", required=True,
                        help="File .jsonl hoac thu muc chua cac file cases*.jsonl")
    parser.add_argument("--llm", choices=("real", "stub"), default="real")
    parser.add_argument("--repeat", type=int, default=1,
                        help="So lan chay lai de bao cao variance (architecture.md muc 5.7)")
    parser.add_argument("--out-dir", default=str(REPORT_DIR))
    args = parser.parse_args()

    if args.llm == "stub":
        os.environ["AGENT_LLM"] = "stub"

    cases = load_cases(Path(args.eval_set))
    if not cases:
        raise SystemExit(f"Khong tim thay case nao co oracle trong {args.eval_set}")

    results = []
    for _round in range(args.repeat):
        for case in cases:
            results.append(grade_case(case, run_one(case)))

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "dataset_version": dataset_version(),
        "llm_mode": args.llm,
        "repeat": args.repeat,
        **aggregate(results),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out_dir / f"autoeval_{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"autoeval_{stamp}.md").write_text(to_markdown(report), encoding="utf-8")

    print(to_markdown(report))
    print(f"Da ghi reports/autoeval_{stamp}.json va .md")


if __name__ == "__main__":
    main()
