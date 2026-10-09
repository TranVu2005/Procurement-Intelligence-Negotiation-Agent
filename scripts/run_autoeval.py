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
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.eval.scoring import METRIC_NAMES, aggregate, grade_case, round_spread  # noqa: E402
from src.llm import model_identity  # noqa: E402
from src.logging_utils.tracer import redact  # noqa: E402

VERSION_PATH = ROOT / "src" / "tools" / "mock_data" / "VERSION"
REPORT_DIR = ROOT / "reports"


def case_tiers(case: dict) -> list[str]:
    tier = case.get("tier", ["pipeline", "llm"])
    tiers = [tier] if isinstance(tier, str) else tier
    if not isinstance(tiers, list) or not tiers or any(t not in ("pipeline", "llm") for t in tiers):
        raise ValueError(f"tier khong hop le cho case {case.get('id')}")
    return tiers


def load_cases(target: Path, tier: str = "all") -> list[dict]:
    paths = sorted(target.glob("cases*.jsonl")) if target.is_dir() else [target]
    cases = []
    for path in paths:
        skipped = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = json.loads(line)
                if "oracle" not in case:
                    skipped += 1
                elif tier == "all" or tier in case_tiers(case):
                    cases.append(case)
        if skipped:
            print(f"CANH BAO: bo qua {skipped} case khong co oracle trong {path}", file=sys.stderr)
    return cases


def run_one(case: dict, sleep_between: float = 0) -> dict:
    from src.graph import run_request

    final = {}
    session_id = None
    requests = []
    for index, turn in enumerate(case["turns"]):
        if index and sleep_between:
            time.sleep(sleep_between)
        final = run_request(turn, session_id=session_id, _inject=case.get("inject"))
        session_id = final.get("session_id") or session_id
        requests.append({**{key: final.get(key) for key in (
            "latency_ms", "llm_ms", "tool_ms", "other_ms", "tokens_in", "tokens_out", "llm_calls")},
            "tool_calls": sum(e.get("status") != "blocked" for e in final.get("tool_results") or []),
            "model": model_identity()["model"], "trace_id": final.get("trace_id")})
    final["_requests"] = requests
    final["model"] = model_identity()["model"]
    return final


def dataset_version() -> str:
    try:
        return VERSION_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def to_markdown(report: dict) -> str:
    def show(value):
        return "không đo được" if value is None else str(value)
    tiers = report.get("tiers") or {"pipeline": report, "llm": report}
    pipeline, llm = tiers["pipeline"], tiers["llm"]
    lines = [
        "# Báo cáo AutoEval hai tầng",
        "",
    ]
    if report["llm_mode"] == "stub" and report.get("tier", "all") in ("llm", "all"):
        lines += ["> **CẢNH BÁO: Tầng 2 chạy StubLLM; số này KHÔNG đánh giá năng lực LLM thật.**", ""]
    lines += [
        f"- Thoi diem: {report['generated_at']}",
        f"- dataset_version: {report['dataset_version']}",
        f"- So case: {report['total_cases']}  |  So lan lap: {report['repeat']}",
        f"- LLM: {report['llm_mode']}",
        f"- Model: {report.get('model', 'unknown')} | provider: {report.get('provider', 'unknown')}",
        f"- Tầng chọn: {report.get('tier', 'all')} | case duy nhất: {report.get('case_count', report['total_cases'])}",
        f"- Requests: {report.get('total_requests', report['total_cases'])} | sleep-between: {report.get('sleep_between', 0)}s",
        "",
        "## Tầng 1 — Kiểm thử pipeline",
        "",
        "| Chi so | Gia tri |",
        "|---|---|",
    ]
    for name in METRIC_NAMES[1:]:
        lines.append(f"| {name} | {show(pipeline['metrics'][name])} |")
    lines += ["", "## Tầng 2 — Năng lực LLM", "", "| Nhóm | Case | Pass | Không đo được | Task success |",
              "|---|---|---|---|---|"]
    for category, item in llm.get("by_category", {}).items():
        lines.append(f"| {category} | {item['total_cases']} | {item['passed_cases']} | "
                     f"{item['unmeasurable_cases']} | {show(item['task_success_rate'])} |")
    lines += ["", "| Chỉ số | Giá trị |", "|---|---|"]
    for name in ("task_success_rate", "intent_routing_accuracy", "field_accuracy", "no_invented_numbers"):
        lines.append(f"| {name} | {show(llm['metrics'].get(name))} |")
    lines += ["", "| Trường trích xuất | Đúng | Đã kiểm | Thiếu | Accuracy |", "|---|---|---|---|---|"]
    for field, item in llm.get("by_field", {}).items():
        lines.append(f"| {field} | {item['correct']} | {item['checked']} | {item['unmeasurable']} | {show(item['accuracy'])} |")
    lines += ["", "## Vận hành", "", "| Chỉ số | Giá trị |", "|---|---|"]
    for key in ("latency_avg_ms", "latency_p50_ms", "latency_p95_ms", "latency_max_ms",
                "llm_p50_ms", "llm_p95_ms", "tool_p50_ms", "tool_p95_ms", "other_p50_ms",
                "avg_llm_calls", "avg_tool_calls", "avg_tokens_in", "avg_tokens_out"):
        lines.append(f"| {key} | {show(report.get(key))} |")
    for key in ("estimated_cost_avg_usd", "estimated_cost_total_usd"):
        lines.append(f"| {key} | {show(report.get(key)) if report.get(key) is not None else 'chưa cấu hình giá'} |")
    lines += ["", "## Diễn giải", "",
              "Tầng 1 kiểm tra implementation, KHÔNG chứng minh năng lực hiểu ngôn ngữ. "
              "Số tầng 2 chỉ có giá trị khi llm_mode=real. Case thiếu field A/B được ghi không đo được, không tính là pass.",
              "Latency/chi phí lấy trên từng request (từng lượt), task success chấm state cuối của case. "
              "Tool latency gồm retry/backoff. Percentile dùng nearest-rank.",
              "No-invented-numbers dùng grader heuristic hiện có: chỉ kiểm số từ 100 trở lên; "
              "không chứng minh toàn bộ con số nhỏ hay sự gắn nguồn trong văn bản. Giá token cần nguồn/ngày chính thức."]
    spread = report.get("spread") or {}
    if report.get("repeat", 1) > 1 and spread:
        lines += ["", "## Do dao dong qua cac lan chay", "",
                  "| Chi so | min | max | stdev |", "|---|---|---|---|"]
        for name, item in spread.items():
            lines.append(f"| {name} | khong do duoc | | |" if item is None
                         else f"| {name} | {item['min']} | {item['max']} | {item['stdev']} |")
    lines += ["", "## Case truot", ""]
    if not report["failed_cases"]:
        lines.append("Khong co case nao truot.")
    for item in report["failed_cases"]:
        lines.append(f"- **{item['id']}** ({item['category']}): {'; '.join(item['failures'])}")
    if report.get("unmeasurable_cases"):
        lines += ["", "## Case không đo được", ""]
        lines += [f"- {item['id']}: {'; '.join(item['reasons'])}" for item in report['unmeasurable_cases']]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", required=True,
                        help="File .jsonl hoac thu muc chua cac file cases*.jsonl")
    parser.add_argument("--llm", choices=("real", "stub"), default="real")
    parser.add_argument("--repeat", type=int, default=1,
                        help="So lan chay lai de bao cao variance (architecture.md muc 5.7)")
    parser.add_argument("--out-dir", default=str(REPORT_DIR))
    parser.add_argument("--tier", choices=("pipeline", "llm", "all"), default="all")
    parser.add_argument("--sleep-between", type=float, default=0)
    args = parser.parse_args()

    if args.repeat < 1 or args.sleep_between < 0:
        parser.error("repeat phai >= 1; sleep-between phai >= 0")
    os.environ["AGENT_LLM"] = args.llm

    cases = load_cases(Path(args.eval_set), args.tier)
    if not cases:
        raise SystemExit(f"Khong tim thay case nao co oracle trong {args.eval_set}")

    per_round = []
    first = True
    for _round in range(args.repeat):
        round_results = []
        for case in cases:
            if not first and args.sleep_between:
                time.sleep(args.sleep_between)
            first = False
            round_results.append(grade_case(case, run_one(case, args.sleep_between)))
        per_round.append(round_results)
    results = [result for round_results in per_round for result in round_results]

    report = {
        "generated_at": datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds"),
        "dataset_version": dataset_version(),
        "llm_mode": args.llm,
        "repeat": args.repeat,
        "case_count": len(cases), "tier": args.tier, "sleep_between": args.sleep_between,
        **model_identity(),
        **aggregate(results),
        "spread": round_spread([aggregate(round_results) for round_results in per_round]),
        "tiers": {tier: aggregate([r for r in results if tier in case_tiers(r)])
                  for tier in ("pipeline", "llm")},
        "tier_spread": {tier: round_spread([aggregate([r for r in rr if tier in case_tiers(r)])
                                           for rr in per_round]) for tier in ("pipeline", "llm")},
        "results": results,
    }
    report = redact(report)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out_dir / f"autoeval_{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"autoeval_{stamp}.md").write_text(to_markdown(report), encoding="utf-8")

    print(to_markdown(report))
    print(f"Da ghi {out_dir / f'autoeval_{stamp}.json'} va .md")


if __name__ == "__main__":
    main()
