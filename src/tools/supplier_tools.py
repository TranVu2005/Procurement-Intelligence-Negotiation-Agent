"""LangChain Tool wrappers doc mock dataset nha cung cap.

Owner: Nguoi C
Tool contract (see PROJECT-SETUP.md section 5): input Pydantic schema,
tra JSON co field ro rang, khong tra text tu do.
"""

import json
from pathlib import Path

MOCK_DATA_PATH = Path(__file__).parent / "mock_data" / "suppliers.json"


def load_suppliers() -> list[dict]:
    return json.loads(MOCK_DATA_PATH.read_text(encoding="utf-8"))


def search_suppliers(product_type: str) -> list[dict]:
    return [s for s in load_suppliers() if s["LoaiSanPham"] == product_type]
