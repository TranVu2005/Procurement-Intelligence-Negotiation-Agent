"""
Tool contract implementation - khop voi interface-contracts.md muc 3 /
SYSTEM-RULES.md muc 2.3. C so huu file nay; B goi qua LangChain Tool
wrapper (khong sua logic loi trong day ma khong cap nhat interface-contracts.md
truoc).

Load du lieu tu mock_data/suppliers.json (sinh boi generate_mock_data.py).
"""

import json
import time
import unicodedata
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.logging_utils.tracer import log_event, log_tool_call, new_trace_id

DATA_PATH = Path(__file__).parent / "mock_data" / "suppliers.json"


def _load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize(text: str | None) -> str | None:
    """Bo dau, ha thuong, gop khoang trang/underscore de so khop khong phan biet
    dinh dang giua tieng Viet co dau (A xuat ra tu Gemini) va slug khong dau
    (mock data). Chi dung de SO SANH, khong lam thay doi gia tri goc tra ve."""
    if text is None:
        return None
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("_", " ").strip().lower()
    return " ".join(text.split())


def _error(error_type: str, message: str) -> dict:
    # Format loi CHUAN - moi tool loi phai tra dung cau truc nay (muc 2.3)
    return {"error": True, "error_type": error_type, "message": message}


def search_suppliers(product_type: str, material: str | None = None, region: str | None = None,
                      _simulate_error: str | None = None) -> dict:
    """
    Input: {"product_type": str (required), "material": str|null, "region": str|null}
    Output: {"suppliers": [{"MaNCC","TenNCC","Gia","MOQ","ThoiGianGiao","DiemUyTin"}]}
    _simulate_error: chi dung trong test (vd "timeout") de gia lap loi ha tang.
    """
    trace_id = new_trace_id()
    start = time.perf_counter()
    params = {"product_type": product_type, "material": material, "region": region}
    log_event(trace_id, "tool_call_start", tool_name="search_suppliers", **params)

    if _simulate_error:
        result = _error(_simulate_error, f"Gia lap loi '{_simulate_error}' cho search_suppliers")
        log_tool_call(trace_id, "search_suppliers", start, "error", params=params)
        return result

    if not product_type:
        result = _error("invalid_input", "product_type la truong bat buoc")
        log_tool_call(trace_id, "search_suppliers", start, "error", params=params)
        return result

    data = _load_data()
    norm_product_type = _normalize(product_type)
    matches = [r for r in data if _normalize(r.get("LoaiSanPham")) == norm_product_type]
    if material:
        norm_material = _normalize(material)
        matches = [r for r in matches if _normalize(r.get("ChatLieu")) == norm_material]
    if region:
        norm_region = _normalize(region)
        matches = [r for r in matches if _normalize(r.get("KhuVuc")) == norm_region]

    if not matches:
        filters = [f"product_type='{product_type}'"]
        if material:
            filters.append(f"material='{material}'")
        if region:
            filters.append(f"region='{region}'")
        result = _error("no_match", f"Khong tim thay nha cung cap voi bo loc: {', '.join(filters)}")
        log_tool_call(trace_id, "search_suppliers", start, "error", params=params)
        return result

    suppliers = [
        {
            "MaNCC": r["MaNCC"],
            "TenNCC": r["TenNCC"],
            # .get() thay vi r[...]: dataset thieu field khong duoc lam crash ca
            # response (cung nguyen tac voi compare_price, muc 3 interface-contracts.md)
            "Gia": r.get("Gia"),
            "MOQ": r.get("MOQ"),
            "ThoiGianGiao": r.get("ThoiGianGiao"),
            "DiemUyTin": r.get("DiemUyTin"),
        }
        for r in matches
    ]
    log_tool_call(trace_id, "search_suppliers", start, "ok", params=params, result_count=len(suppliers))
    return {"suppliers": suppliers}


def get_supplier_detail(supplier_id: str, _simulate_error: str | None = None) -> dict:
    """
    Input: {"supplier_id": str (required)}
    Output: full record 13 field, hoac error format neu khong tim thay.
    """
    trace_id = new_trace_id()
    start = time.perf_counter()
    params = {"supplier_id": supplier_id}
    log_event(trace_id, "tool_call_start", tool_name="get_supplier_detail", **params)

    if _simulate_error:
        result = _error(_simulate_error, f"Gia lap loi '{_simulate_error}' cho get_supplier_detail")
        log_tool_call(trace_id, "get_supplier_detail", start, "error", params=params)
        return result

    if not supplier_id:
        result = _error("invalid_input", "supplier_id la truong bat buoc")
        log_tool_call(trace_id, "get_supplier_detail", start, "error", params=params)
        return result

    data = _load_data()
    for r in data:
        if r["MaNCC"] == supplier_id:
            log_tool_call(trace_id, "get_supplier_detail", start, "ok", params=params)
            return r  # da dung 13 field theo dinh nghia

    result = _error("no_match", f"Khong tim thay supplier_id='{supplier_id}'")
    log_tool_call(trace_id, "get_supplier_detail", start, "error", params=params)
    return result


def _apply_discount(price: int, quantity: int, tiers: list[dict]) -> tuple[int, int]:
    """Chon bac giam gia cao nhat ma quantity dat duoc. Tra ve (unit_price, phan_tram_giam)."""
    applicable = [t for t in (tiers or []) if quantity >= t["tu_so_luong"]]
    if not applicable:
        return price, 0
    best = max(applicable, key=lambda t: t["phan_tram_giam"])
    pct = best["phan_tram_giam"]
    unit_price = round(price * (1 - pct / 100))
    return unit_price, pct


def compare_price(supplier_ids: list[str], quantity: int) -> dict:
    """
    Input: {"supplier_ids": [str], "quantity": int (required)}
    Output: {"comparisons": [{"MaNCC","unit_price","discount_applied","total_price","meets_moq"}]}
    Neu 1 supplier_id loi -> tra loi CHO RIENG phan tu do, khong fail ca response (muc 2.3).
    """
    trace_id = new_trace_id()
    start = time.perf_counter()
    params = {"supplier_ids": supplier_ids, "quantity": quantity}
    log_event(trace_id, "tool_call_start", tool_name="compare_price", **params)

    # --- validate-first: chan het truoc khi dung data, khong de loi throw giua chung ---
    if not quantity or quantity <= 0:
        result = _error("invalid_input", "quantity phai la so nguyen duong")
        log_tool_call(trace_id, "compare_price", start, "error", params=params)
        return result

    if not supplier_ids:
        result = _error("invalid_input", "supplier_ids phai co it nhat 1 phan tu")
        log_tool_call(trace_id, "compare_price", start, "error", params=params)
        return result

    data = _load_data()
    index = {r["MaNCC"]: r for r in data}

    comparisons = []
    for sid in supplier_ids:
        record = index.get(sid)
        if record is None:
            comparisons.append({
                "MaNCC": sid,
                **_error("no_match", f"supplier_id='{sid}' khong ton tai"),
            })
            continue

        try:
            unit_price, pct = _apply_discount(record["Gia"], quantity, record.get("ChietKhauTheoSoLuong"))
            comparisons.append({
                "MaNCC": sid,
                "unit_price": unit_price,
                "discount_applied": f"{pct}%",
                "total_price": unit_price * quantity,
                "meets_moq": quantity >= record["MOQ"],
            })
        except KeyError as e:
            # dataset thieu field (vd Gia/MOQ) -> loi rieng phan tu nay, khong fail ca response
            comparisons.append({
                "MaNCC": sid,
                **_error("tool_unavailable", f"Du lieu NCC '{sid}' thieu truong {e}"),
            })

    error_count = sum(1 for c in comparisons if c.get("error"))
    status = "error" if error_count == len(comparisons) else "ok"
    log_tool_call(trace_id, "compare_price", start, status, params=params,
                  result_count=len(comparisons), error_count=error_count)
    return {"comparisons": comparisons}


# --- LangChain Tool wrapper (B goi qua day; args_schema chi lo public field,
# khong expose _simulate_error - do chi de test noi bo) ---

class SearchSuppliersArgs(BaseModel):
    product_type: str = Field(
        description="Loại sản phẩm cần tìm. Phải là 1 trong các giá trị catalog hiện có: "
        "'ghế văn phòng', 'bàn làm việc', 'tủ hồ sơ', 'kệ', 'sofa'. Bắt buộc."
    )
    material: str | None = Field(
        default=None,
        description="Lọc theo chất liệu nếu người dùng nêu rõ, vd 'da_that', 'go_tu_nhien'. "
        "Để trống (null) nếu không yêu cầu chất liệu cụ thể.",
    )
    region: str | None = Field(
        default=None,
        description="Lọc theo khu vực nếu người dùng nêu rõ, vd 'Ha Noi', 'TP.HCM'. "
        "Để trống (null) nếu không yêu cầu khu vực cụ thể.",
    )


class GetSupplierDetailArgs(BaseModel):
    supplier_id: str = Field(
        description="Mã nhà cung cấp (MaNCC) đã biết trước, vd 'NCC001'. Bắt buộc, CHỈ 1 mã mỗi lần gọi "
        "-- nếu cần chi tiết nhiều NCC thì gọi tool này nhiều lần riêng biệt, không được truyền mảng."
    )


class ComparePriceArgs(BaseModel):
    supplier_ids: list[str] = Field(
        description="Danh sách MaNCC cần so sánh giá, vd ['NCC001', 'NCC004']. Bắt buộc, ít nhất 1 phần tử."
    )
    quantity: int = Field(
        description="Số lượng dự kiến đặt mua (số nguyên dương). Bắt buộc -- dùng để tính chiết khấu "
        "theo bậc và kiểm tra có đạt MOQ hay không."
    )


search_suppliers_tool = StructuredTool.from_function(
    func=search_suppliers,
    name="search_suppliers",
    description=(
        "Tìm danh sách nhà cung cấp nội thất theo loại sản phẩm, lọc thêm theo chất liệu/khu vực nếu có. "
        "DÙNG KHI: chưa biết MaNCC cụ thể, cần danh sách ứng viên để so sánh hoặc lọc theo ràng buộc. "
        "KHÔNG DÙNG KHI: đã có sẵn MaNCC rồi (dùng get_supplier_detail thay thế); hoặc cần tính giá/kiểm tra "
        "MOQ cho 1 số lượng cụ thể (dùng compare_price thay thế)."
    ),
    args_schema=SearchSuppliersArgs,
)

get_supplier_detail_tool = StructuredTool.from_function(
    func=get_supplier_detail,
    name="get_supplier_detail",
    description=(
        "Lấy đầy đủ 13 trường thông tin gốc của ĐÚNG 1 nhà cung cấp theo MaNCC đã biết. "
        "DÙNG KHI: đã có MaNCC (từ kết quả search_suppliers hoặc người dùng cung cấp sẵn) và cần xem "
        "chi tiết đầy đủ (BaoHanh, TonKho, ChietKhauTheoSoLuong...). "
        "KHÔNG DÙNG KHI: chưa có MaNCC (dùng search_suppliers trước); cần chi tiết nhiều NCC cùng lúc "
        "(gọi tool này lặp lại cho từng MaNCC, không truyền mảng trong 1 lần gọi)."
    ),
    args_schema=GetSupplierDetailArgs,
)

compare_price_tool = StructuredTool.from_function(
    func=compare_price,
    name="compare_price",
    description=(
        "So sánh giá sau chiết khấu theo số lượng và kiểm tra điều kiện MOQ cho 1 danh sách nhà cung cấp. "
        "DÙNG KHI: đã có danh sách MaNCC ứng viên và đã biết rõ số lượng dự kiến đặt mua, cần tính "
        "unit_price/total_price/meets_moq để làm cơ sở leverage score hoặc đề xuất. "
        "KHÔNG DÙNG KHI: chưa biết số lượng cụ thể (phải hỏi người dùng trước, không được tự giả định "
        "quantity); chỉ cần tìm/lọc NCC (dùng search_suppliers) hoặc xem thông tin chung (dùng "
        "get_supplier_detail)."
    ),
    args_schema=ComparePriceArgs,
)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # Vi du nhanh de kiem tra thu cong
    print(json.dumps(search_suppliers("ghế văn phòng"), ensure_ascii=False, indent=2)[:500])
    print(json.dumps(get_supplier_detail("EDGE002"), ensure_ascii=False, indent=2))
    print(json.dumps(compare_price(["EDGE003", "NCC_KHONG_TON_TAI"], quantity=5), ensure_ascii=False, indent=2))
