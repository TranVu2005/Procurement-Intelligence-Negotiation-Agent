"""So sanh bao gia B2B thu tay voi web va thu hang pipeline StubLLM."""

import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.tools.supplier_tools import _normalize


def _rank(records, supplier_id, quote, hard):
    from src.graph import run_request
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "suppliers.json"
        path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        with patch("src.tools.supplier_tools.DATA_PATH", path), patch.dict(os.environ, {
                "AGENT_LLM": "stub", "AGENT_STUB_LATENCY_MEAN_S": "0", "AGENT_STUB_LATENCY_STDDEV_S": "0"}):
            final = run_request("So sanh nguon gia cho thu nghiem B2B", overrides={"perceive": lambda s: {
                "intent": "search_new", "req": {"session_id": "TEST_B2B_COMPARISON",
                    "hard_constraints": hard, "soft_constraints": {}}},
                # Chi bao cao thu hang, khong bien scenario thanh de xuat mua hang.
                "respond": lambda s: {"answer": "Thử nghiệm thứ hạng với nguồn giá đã chọn.", "status": "success"},
                "confirm_gate": lambda s: {}})
    position = next((i for i, r in enumerate(final.get("ranked") or [], 1)
                     if r.get("MaNCC") == supplier_id), None)
    return {"rank": position, "status": final.get("status"), "trace_id": final.get("trace_id")}


def compare_quotes(records, ranker=None):
    ranker = ranker or _rank
    quotes = [r for r in records if r.get("nguon_type") == "b2b_quote"]
    web = [r for r in records if r.get("nguon_type") == "trang_san_pham"]
    rows = []
    for quote in quotes:
        matches = [r for r in web if all(_normalize(r.get(key)) == _normalize(quote.get(key))
                                      for key in ("TenNCC", "LoaiSanPham", "TenSanPham"))]
        row = {"quote_id": quote["MaNCC"], "supplier": quote["TenNCC"],
               "product": quote["TenSanPham"], "quote_price": quote.get("Gia"),
               "quantity": quote["quote_quantity"], "quote_date": quote["quote_date"],
               "quote_url": quote.get("nguon_url"), "web_price": None, "difference_pct": None,
               "web_rank": None, "b2b_rank": None, "reason": None}
        if len(matches) != 1:
            row["reason"] = "không có một bản ghi web khớp duy nhất NCC/sản phẩm"
        elif not matches[0].get("Gia") or not quote.get("Gia"):
            row["reason"] = "thiếu giá có nguồn"
        else:
            match = matches[0]
            row.update(web_id=match["MaNCC"], web_price=match["Gia"], web_url=match.get("nguon_url"),
                       difference_pct=round((quote["Gia"] / match["Gia"] - 1) * 100, 4))
            baseline = [r for r in web if r["LoaiSanPham"] == quote["LoaiSanPham"]]
            replacement = {**match, "Gia": quote["Gia"], "price_source_url": quote["nguon_url"],
                           "quote_quantity": quote["quote_quantity"], "quote_date": quote["quote_date"],
                           "quote_channel": quote["quote_channel"], "nguon_type": "b2b_quote"}
            replacement["field_sources"] = {"Gia": quote["nguon_url"], **{
                field: match["nguon_url"] for field in ("MOQ", "TonKho", "ThoiGianGiao", "BaoHanh", "DiemUyTin")}}
            scenario = [replacement if r["MaNCC"] == match["MaNCC"] else r for r in baseline]
            hard = {"product_type": quote["LoaiSanPham"], "quantity": quote["quote_quantity"],
                    "budget_max": max([quote["Gia"], *(r.get("Gia") or 0 for r in baseline)]) * quote["quote_quantity"],
                    "delivery_deadline_days": max(r.get("ThoiGianGiao") or 0 for r in baseline)}
            row["experiment_constraints"] = hard
            row["web_run"] = ranker(baseline, match["MaNCC"], quote, hard)
            row["b2b_run"] = ranker(scenario, match["MaNCC"], quote, hard)
            row["web_rank"], row["b2b_rank"] = row["web_run"]["rank"], row["b2b_run"]["rank"]
        rows.append(row)
    return rows


def to_markdown(rows):
    lines = ["# So sánh báo giá B2B với giá web", "",
             "Thứ hạng chạy pipeline stub với req có cấu trúc, không đánh giá hiểu ngôn ngữ. "
             "Giữ số lượng báo giá; ngân sách/thời hạn thử nghiệm lấy trần từ dataset. "
             "Hai lần chạy dùng cùng request và thuộc tính ngoài giá từ web; chỉ thay giá. "
             "Giá có nguồn báo B2B, các thuộc tính nghiệp vụ còn lại giữ nguồn web. "
             "Các trường còn mô phỏng phải kiểm tra trước khi mua.", "",
             "| NCC / sản phẩm | SL | Giá web VND | Giá B2B VND | Chênh % | Hạng web | Hạng B2B | Bằng chứng |",
             "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        value = lambda key: row.get(key) if row.get(key) is not None else "không đo được"
        lines.append(f"| {row['supplier']} / {row['product']} | {row['quantity']} | {value('web_price')} | "
                     f"{value('quote_price')} | {value('difference_pct')} | {value('web_rank')} | "
                     f"{value('b2b_rank')} | {row.get('web_id', '')} {row.get('web_url', '')}; "
                     f"{row['quote_id']} {row['quote_url']} {row['quote_date']} |")
        if row["reason"]:
            lines.append(f"\n- {row['quote_id']}: {row['reason']}")
        if row.get("experiment_constraints"):
            lines.append(f"\n- {row['quote_id']} — điều kiện thử nghiệm cố định: {row['experiment_constraints']}; "
                         f"trace web={row['web_run'].get('trace_id')}, B2B={row['b2b_run'].get('trace_id')}.")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "src/tools/mock_data/suppliers.json")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--llm", choices=("stub",), default="stub")
    args = parser.parse_args()
    rows = compare_quotes(json.loads(args.dataset.read_text(encoding="utf-8")))
    if not rows:
        print("chưa có báo giá b2b_quote nào")
        return
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"b2b_vs_web_{date.today().isoformat()}.md"
    path.write_text(to_markdown(rows), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
