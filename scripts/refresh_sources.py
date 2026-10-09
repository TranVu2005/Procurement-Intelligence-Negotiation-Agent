"""Lam moi nguon web, giu nguyen bao gia thu tay. --dry-run khong goi mang."""

import argparse
import csv
import sys
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import verify_sources
from generate_mock_data import generate_dataset
from src.tools.dataset_builder import read_source_rows, validate_rows


def refresh(dry_run=False, sources_dir=None, output_dir=None, cache_dir=None, today=None):
    sources_dir = Path(sources_dir or ROOT / "src/tools/mock_data/sources")
    output_dir = Path(output_dir or ROOT / "src/tools/mock_data")
    today = today or date.today()
    paths = sorted(sources_dir.glob("*.csv"))
    rows = read_source_rows(paths)
    validate_rows(rows)
    if dry_run:
        return {"dry_run": True, "web_rows": sum(r.get("nguon_type") != "b2b_quote" for r in rows),
                "sources_dir": str(sources_dir), "output_dir": str(output_dir)}
    changes, staged = [], []
    run_cache = Path(cache_dir) / uuid.uuid4().hex if cache_dir else None
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames
            source_rows = list(reader)
        web_rows = [row for row in source_rows if any(row.values())
                    and not (row.get("supplier_name") or "").startswith("#")
                    and row.get("nguon_type") != "b2b_quote"]
        if not web_rows:
            continue
        # Cache la snapshot cua lan fetch nay, khong replay HTML cu thanh gia moi.
        file_cache = run_cache / path.stem if run_cache else None
        if file_cache:
            file_cache.mkdir(parents=True, exist_ok=True)
        report = verify_sources.verify(web_rows, file_cache)
        changes.extend(verify_sources.apply(web_rows, report, today.isoformat()))
        validate_rows([row for row in source_rows if any(row.values())
                       and not (row.get("supplier_name") or "").startswith("#")])
        staged.append((path, columns, source_rows))
    for path, columns, source_rows in staged:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(source_rows)
    records, version = generate_dataset(sources_dir, output_dir / "suppliers.json",
                                        output_dir / "VERSION", today.isoformat())
    return {"dry_run": False, "changes": changes, "records": len(records), "dataset_version": version}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    print(refresh(dry_run=args.dry_run, cache_dir=args.cache_dir))


if __name__ == "__main__":
    main()
