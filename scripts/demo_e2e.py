"""Demo end-to-end 1 cau hoi mau: Perception (A) -> Reasoning (B) -> Tool (C).

Dung cho buoi hop doi chieu field giua 3 module. Neu parser cua A chua chay
duoc (thieu GOOGLE_API_KEY that), tu dong fallback sang state mau co san
(session_states_sample.json) de van demo duoc phan B + C.
"""

import json
import sys
from pathlib import Path

SAMPLE_TEXT = "Can mua 20 ghe van phong ngan sach 40 trieu, giao trong 10 ngay, uu tien vai boc o Ha Noi"


def get_state() -> dict:
    try:
        from src.perception.parser import parse_request
        return parse_request(SAMPLE_TEXT)
    except Exception as exc:  # noqa: BLE001 -- demo fallback, in ro nguyen nhan
        print(f"[A - Perception] khong chay duoc ({exc.__class__.__name__}: {exc})")
        print("[A - Perception] fallback sang state mau session_states_sample.json (sess_001)")
        sample_path = Path(__file__).parent.parent / "session_states_sample.json"
        return json.loads(sample_path.read_text(encoding="utf-8"))["sess_001"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 70)
    print("[A - PERCEPTION] Input:", SAMPLE_TEXT)
    state = get_state()
    print("[A - PERCEPTION] State:", json.dumps(state, ensure_ascii=False, indent=2))

    print("=" * 70)
    from src.reasoning.planner import make_plan
    plan = make_plan(state)
    step = plan["steps"][0]
    print("[B - REASONING] Plan action:", step["action"])
    print("[B - REASONING] Plan params:", step["params"])

    print("=" * 70)
    from src.tools.supplier_tools import search_suppliers_tool
    result = search_suppliers_tool.invoke(step["params"])
    print("[C - TOOL] search_suppliers ->", len(result.get("suppliers", [])), "ket qua")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:800])


if __name__ == "__main__":
    main()
