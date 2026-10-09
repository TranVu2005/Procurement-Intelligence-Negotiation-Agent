"""Load test cho run_request. Owner: Nguoi C.

Cach chay:
    python scripts/run_loadtest.py --levels 1,5 --llm real
    python scripts/run_loadtest.py --levels 10,20,50 --llm stub

Muc 1-5 CCU goi Gemini that; muc 10-50 CCU chay voi --llm stub vi de tranh
rate limit va vi o muc do khong con do duoc gi ve mo hinh. Bao cao BAT BUOC
ghi ro muc nao dung LLM that, muc nao dung stub (architecture.md muc 5.6).
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psutil  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.graph import run_request  # noqa: E402
from src.eval.scoring import distribution_stats  # noqa: E402
from src.llm import model_identity  # noqa: E402
from src.logging_utils.tracer import redact  # noqa: E402

DEFAULT_PROMPT = "Can 50 ghe van phong, ngan sach 200 trieu, giao trong 14 ngay, uu tien Ha Noi"
REPORT_DIR = ROOT / "reports"

# Trang thai duoc tinh la thanh cong khi do tai
_OK_STATUSES = {"success", "needs_confirmation"}


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * len(ordered)) - 1))
    return ordered[index]


def to_markdown(report: dict) -> str:
    stub = report.get("stub_latency")
    mode = report["llm_mode"]
    if stub:
        mode = (f"stub (mean={stub['mean_s']}s, stddev={stub['stddev_s']}s moi lan goi LLM, "
                "2 lan goi/request)")
    lines = [
        "# Bao cao load test",
        "",
        f"- Thoi diem: {report['generated_at']}",
        f"- LLM: {mode}",
        f"- Prompt: {report['prompt']}",
        "",
        "| CCU | req | rps | p50_ms | p95_ms | error_rate | cpu% | rss_mb |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for level in report["levels"]:
        lines.append(
            f"| {level['concurrency']} | {level['requests']} | {level['throughput_rps']} | "
            f"{level['latency_p50_ms']} | {level['latency_p95_ms']} | {level['error_rate']} | "
            f"{level['cpu_percent']} | {level['rss_mb']} |"
        )
    lines += ["", "| CCU | LLM p50_ms | LLM p95_ms | Tool p50_ms | Tool p95_ms | Other p50_ms |", "|---|---|---|---|---|---|"]
    for level in report["levels"]:
        lines.append(f"| {level['concurrency']} | {level.get('llm_p50_ms')} | {level.get('llm_p95_ms')} | "
                     f"{level.get('tool_p50_ms')} | {level.get('tool_p95_ms')} | {level.get('other_p50_ms')} |")
    lines += ["", "LLM time là thời gian node perceive + respond (gồm parse/wiring); tool time gồm retry/backoff. "
              "Stub latency bằng 0 chỉ đo pipeline, không đại diện hiệu năng API thật."]
    return "\n".join(lines) + "\n"


def _one_request(prompt: str) -> dict:
    started = time.perf_counter()
    try:
        final = run_request(prompt)
        ok = final.get("status") in _OK_STATUSES
    except Exception:  # noqa: BLE001 - mot request hong khong duoc dung ca phep do
        ok = False
        final = {}
    return {"latency_ms": round((time.perf_counter() - started) * 1000, 2), "ok": ok,
            **{key: final.get(key) for key in ("llm_ms", "tool_ms", "other_ms", "trace_id")}}


def run_level(prompt: str, concurrency: int, requests_per_level: int) -> dict:
    process = psutil.Process()
    process.cpu_percent(interval=None)  # goi lan dau de moc chuan

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        outcomes = list(pool.map(lambda _i: _one_request(prompt), range(requests_per_level)))
    elapsed_s = time.perf_counter() - started

    latencies = [r["latency_ms"] for r in outcomes]
    errors = sum(1 for r in outcomes if not r["ok"])
    components = {}
    for key in ("llm_ms", "tool_ms", "other_ms"):
        components.update({f"{key.removesuffix('_ms')}_{name}_ms": value
                           for name, value in distribution_stats([r[key] for r in outcomes]).items()})
    return {
        "concurrency": concurrency,
        "requests": requests_per_level,
        "elapsed_s": round(elapsed_s, 3),
        "throughput_rps": round(requests_per_level / elapsed_s, 3) if elapsed_s else 0.0,
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "error_rate": round(errors / requests_per_level, 4),
        "cpu_percent": process.cpu_percent(interval=None),
        "rss_mb": round(process.memory_info().rss / 1024 / 1024, 1),
        **components,
        "request_measurements": outcomes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", default="1,5,10,20,50")
    parser.add_argument("--requests-per-level", type=int, default=20)
    parser.add_argument("--llm", choices=("real", "stub"), default="stub")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--out-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args()

    os.environ["AGENT_LLM"] = args.llm

    levels = [int(x) for x in args.levels.split(",") if x.strip()]
    if not levels or any(level < 1 for level in levels) or args.requests_per_level < 1:
        parser.error("levels va requests-per-level phai duong")
    report = {
        "generated_at": datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds"),
        "llm_mode": args.llm,
        "prompt": args.prompt,
        **model_identity(),
        "levels": [run_level(args.prompt, level, args.requests_per_level) for level in levels],
    }

    if args.llm == "stub":
        from src.llm import stub_latency_settings
        report["stub_latency"] = stub_latency_settings()

    report = redact(report)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = args.out_dir / f"loadtest_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = args.out_dir / f"loadtest_{stamp}.md"
    md_path.write_text(to_markdown(report), encoding="utf-8")

    print(f"LLM: {args.llm}")
    print(f"{'CCU':>5} {'rps':>8} {'p50_ms':>10} {'p95_ms':>10} {'err':>6} {'cpu%':>6} {'rss_mb':>8}")
    for level in report["levels"]:
        print(f"{level['concurrency']:>5} {level['throughput_rps']:>8} "
              f"{level['latency_p50_ms']:>10} {level['latency_p95_ms']:>10} "
              f"{level['error_rate']:>6} {level['cpu_percent']:>6} {level['rss_mb']:>8}")
    print(f"\nDa ghi {path} va {md_path}")


if __name__ == "__main__":
    main()
