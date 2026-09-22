"""Doi chieu tung dong nguon voi trang san pham that, xuat bao cao va (tuy chon) cap nhat CSV.

Chay:
    python scripts/verify_sources.py                      # chi bao cao
    python scripts/verify_sources.py --apply              # bao cao + cap nhat CSV nguon
    python scripts/verify_sources.py --cache-dir <dir>    # dung lai HTML da tai

Ket qua: reports/source_verification_<ngay>.csv. Sau --apply phai chay lai
`python generate_mock_data.py` de sinh suppliers.json.

Quy tac cap nhat (--apply):
- price: gia ban hien tai tren trang. Trang Hoa Phat co bien the (so cho, chat lieu
  boc...) thi gia phai gan voi DUNG mot bien the: giu bien the co gia trung CSV, neu
  khong co thi lay bien the mac dinh tren trang; ten bien the duoc ghi vao product_name.
  Trang "Lien he" -> de trong, khong doan.
- material: chi dien khi CSV trong. CSV da co ma trang noi khac -> bao cao
  material_conflict, nguoi sua tay (khong tu ghi de).
- warranty_months: chi dien khi CSV trong va trang ghi thoi han cu the.
- collected_at: ngay chay script voi moi dong doc duoc trang.
- note: ghi gia goc/gach ngang, bien the, VAT va doan chat lieu tren trang de nguoi duyet.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.dataset_builder import SOURCE_COLUMNS  # noqa: E402
from src.tools.source_verify import (  # noqa: E402
    _text,
    compare_row,
    extract_material,
    extract_offer,
    extract_warranty_months,
    hoa_phat_variant_combos,
    normalize_material,
    parse_vnd,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE_CSV = ROOT / "src" / "tools" / "mock_data" / "sources" / "c_sourced_products.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "Chrome/120 Safari/537.36"}
HOA_PHAT_PRICE_API = "https://noithathoaphat.com.vn/hp_variation_price.php"
TODAY = date.today().isoformat()

# Nhan chat lieu boc cua bien the Hoa Phat -> nhan dataset
_VARIANT_MATERIAL = {"bọc da thật": "da_that", "bọc pvc": "da_cong_nghiep",
                     "bọc vải": "vai_boc"}


def fetch(url: str, cache: Path | None, index: int) -> tuple[int, str]:
    cached = cache / f"{index:03d}.html" if cache else None
    if cached and cached.exists():
        return 200, cached.read_text(encoding="utf-8")
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if cached and response.status_code == 200:
                cached.write_text(response.text, encoding="utf-8")
            return response.status_code, response.text
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return 0, ""


def variant_prices(page: str) -> list[dict]:
    """Gia tung to hop bien the Hoa Phat qua API cua chinh trang do."""
    product_id, combos = hoa_phat_variant_combos(page)
    priced = []
    for combo in combos:
        try:
            data = requests.get(HOA_PHAT_PRICE_API, headers=HEADERS, timeout=30, params={
                "productid": product_id, "options": combo["option_ids"]}).json()
        except (requests.RequestException, ValueError):
            data = {}
        price = parse_vnd(data.get("price")) if data.get("success") else None
        priced.append({**combo, "price": price, "sku": data.get("sku")})
        time.sleep(0.5)
    return priced


def pick_variant(csv_price: int | None, variants: list[dict]) -> dict | None:
    same = [v for v in variants if v["price"] is not None and v["price"] == csv_price]
    if same:
        return same[0]
    default = [v for v in variants if v["default"] and v["price"] is not None]
    return default[0] if default else None


def variant_material(label: str) -> str | None:
    lowered = label.lower()
    for key, value in _VARIANT_MATERIAL.items():
        if key in lowered:
            return value
    return None


def verify(rows: list[dict], cache: Path | None) -> list[dict]:
    report = []
    for index, row in enumerate(rows, 1):
        status, page = fetch(row["source_url"], cache, index)
        offer = extract_offer(row["source_url"], page) if status == 200 else {
            "price": None, "regular_price": None, "status": f"http_{status}"}
        variants = variant_prices(page) if status == 200 else []
        chosen = pick_variant(int(row["price"]) if row["price"] else None, variants)
        if chosen:
            offer = {**offer, "price": chosen["price"], "status": "ok"}
        raw_material = extract_material(page) if status == 200 else None
        text = _text(page) if status == 200 else ""
        entry = {
            "row": index,
            "supplier_name": row["supplier_name"],
            "product_name": row["product_name"],
            "source_url": row["source_url"],
            "http_status": status,
            "csv_price": row["price"],
            "page_price": offer.get("price"),
            "regular_price": offer.get("regular_price"),
            "price_status": compare_row(row, offer),
            "variant_used": chosen["label"] if chosen else "",
            "variant_table": "; ".join(f"{v['label']}={v['price']}" for v in variants),
            "csv_material": row["material"],
            "page_material_text": raw_material or "",
            "page_material": (variant_material(chosen["label"]) if chosen else None)
                             or normalize_material(raw_material, row["product_type"]) or "",
            "csv_warranty": row["warranty_months"],
            "page_warranty": extract_warranty_months(page) if status == 200 else None,
            "ex_vat": "Giá chưa có VAT" in text,
        }
        entry["material_status"] = (
            "conflict" if entry["csv_material"] and entry["page_material"]
            and entry["csv_material"] != entry["page_material"] else "ok")
        report.append(entry)
        print(f"{index:3d} {entry['price_status']:18} {row['product_name'][:45]}")
    return report


def apply(rows: list[dict], report: list[dict]) -> list[str]:
    changes = []
    for row, entry in zip(rows, report):
        if entry["http_status"] != 200:
            continue
        label = f"dong {entry['row']} ({row['product_name'][:40]})"
        if entry["price_status"] == "price_mismatch":
            changes.append(f"{label}: price {row['price']} -> {entry['page_price']}")
            row["price"] = str(entry["page_price"])
        elif entry["price_status"] == "price_not_found" and not entry["variant_used"]:
            changes.append(f"{label}: price {row['price']} -> (trong, trang khong co gia)")
            row["price"] = ""
        if entry["variant_used"] and entry["variant_used"] not in row["product_name"]:
            row["product_name"] = f"{row['product_name']} - {entry['variant_used']}"
            changes.append(f"{label}: ghi ro bien the '{entry['variant_used']}'")
        if not row["material"] and entry["page_material"]:
            row["material"] = entry["page_material"]
            changes.append(f"{label}: material -> {entry['page_material']}")
        if entry["variant_used"] and entry["page_material"] and \
                row["material"] != entry["page_material"] and variant_material(entry["variant_used"]):
            changes.append(f"{label}: material {row['material']} -> {entry['page_material']} "
                           "(theo bien the co gia trung)")
            row["material"] = entry["page_material"]
        if not row["warranty_months"] and entry["page_warranty"]:
            row["warranty_months"] = str(entry["page_warranty"])
            changes.append(f"{label}: warranty_months -> {entry['page_warranty']}")
        notes = [f"doi chieu {TODAY}"]
        if entry["regular_price"]:
            notes.append(f"gia goc gach ngang tren trang {entry['regular_price']}")
        if entry["variant_used"]:
            notes.append(f"bien the {entry['variant_used']}")
        if entry["ex_vat"]:
            notes.append("gia chua VAT")
        if entry["page_material_text"]:
            notes.append(f"chat lieu tren trang: {entry['page_material_text'][:120]}")
        row["note"] = "; ".join(notes)
        row["collected_at"] = TODAY
    return changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.cache_dir:
        args.cache_dir.mkdir(parents=True, exist_ok=True)

    with SOURCE_CSV.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    report = verify(rows, args.cache_dir)

    out = ROOT / "reports" / f"source_verification_{TODAY}.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report[0]))
        writer.writeheader()
        writer.writerows(report)
    print(f"\nBao cao: {out}")

    if args.apply:
        changes = apply(rows, report)
        with SOURCE_CSV.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(SOURCE_COLUMNS))
            writer.writeheader()
            writer.writerows({col: row.get(col, "") for col in SOURCE_COLUMNS} for row in rows)
        print(f"Da cap nhat {SOURCE_CSV.name}: {len(changes)} thay doi")
        for change in changes:
            print("  -", change)


if __name__ == "__main__":
    main()
