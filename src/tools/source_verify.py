"""Doi chieu du lieu nguon voi trang san pham that. Owner: Nguoi C.

Moi ham o day la tat dinh (regex theo cau truc tung site), khong dung LLM:
gia la so lieu quyet dinh nen phai truy duoc toi dung doan HTML da doc.

Quy uoc gia (SYSTEM-RULES: moi con so phai co nguon):
- price         = gia ban hien tai tren trang (gia sau khuyen mai neu co).
- regular_price = gia goc/gach ngang neu trang co hien, khong thi None.
- status: ok | ambiguous (nhieu bien the khac gia) | contact ("Lien he")
          | not_found (khong doc duoc gia) | http_<code> (trang loi)
"""

from __future__ import annotations

import html as html_lib
import itertools
import json
import re
from urllib.parse import urlparse

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_NUMBER = re.compile(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]00)?(?!\d)|\d{4,}")


def _text(fragment: str) -> str:
    """HTML -> van ban mot dong (bo script/style, giai ma entity)."""
    fragment = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", fragment)
    return _SPACE.sub(" ", html_lib.unescape(_TAG.sub(" ", fragment))).strip()


def parse_vnd(text: str | None) -> int | None:
    """So VND dau tien trong chuoi: '1,927,000vnđ', '450.000₫', '11,400,000.00 ₫'."""
    match = _NUMBER.search(text or "")
    if not match:
        return None
    token = match.group(0)
    token = re.sub(r"[.,]00$", "", token) if re.search(r"[.,]\d{3}[.,]00$", token) else token
    return int(re.sub(r"[.,]", "", token))


def _all_vnd(fragment: str) -> list[int]:
    return [parse_vnd(m.group(0)) for m in _NUMBER.finditer(_text(fragment))]


def _offer(price, regular=None, status="ok", **extra) -> dict:
    if price is None and status == "ok":
        status = "not_found"
    if regular is not None and regular == price:
        regular = None
    return {"price": price, "regular_price": regular, "status": status, **extra}


def _after(page: str, marker: str, length: int = 600) -> str | None:
    index = page.find(marker)
    return None if index < 0 else page[index:index + length]


def _tekkashop(page: str) -> dict:
    match = re.search(r'"variants":\s*\[', page)
    if not match:
        return _offer(None)
    raw = html_lib.unescape(page[match.end() - 1:match.end() + 80000])
    variants, _ = json.JSONDecoder().raw_decode(raw)
    prices = sorted({v["price"] // 100 for v in variants if isinstance(v.get("price"), int)})
    compares = {v["compare_at_price"] // 100 for v in variants
                if isinstance(v.get("compare_at_price"), int)}
    if len(prices) > 1:
        return _offer(None, status="ambiguous", variant_prices=prices)
    regular = max(compares) if compares else None
    return _offer(prices[0] if prices else None, regular)


def _hoa_phat(page: str) -> dict:
    block = _after(page, 'class="hp-product-price"', 300)
    return _offer(parse_vnd(_text(block)) if block else None)


def _hunter(page: str) -> dict:
    block = _after(page, "product-page-price", 800)
    if not block:
        return _offer(None)
    block = block.split('class="quantity"')[0]
    numbers = _all_vnd(block)
    if "price-on-sale" in block[:120] and len(numbers) >= 2:
        return _offer(numbers[1], numbers[0])
    return _offer(numbers[0] if numbers else None)


def _linco(page: str) -> dict:
    def field(name):
        found = re.search(rf'"{name}":"([^"]*)"', page)
        return parse_vnd(found.group(1)) if found else None
    price = field("formattedDiscountedPrice") or field("formattedPrice")
    return _offer(price, field("formattedComparePrice"))


def _gia_ke_pro(page: str) -> dict:
    special = _after(page, 'class="special-price"', 300)
    old = _after(page, 'class="old-price"', 300) or _after(page, 'class="price-old"', 200)
    return _offer(parse_vnd(_text(special)) if special else None,
                  parse_vnd(_text(old)) if old else None)


def _hoaphathcm(page: str) -> dict:
    block = _after(page, 'class="price-new-pro-detail"', 200)
    old = _after(page, 'class="price-old-pro-detail"', 200)
    return _offer(parse_vnd(_text(block)) if block else None,
                  parse_vnd(_text(old)) if old else None)


def _json_ld(page: str) -> dict:
    for script in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page):
        found = re.search(r'"(?:price|lowPrice)"\s*:\s*"?([\d.]+)', script)
        if found:
            value = int(float(found.group(1)))
            if value > 0:
                return _offer(value)
    return _offer(None)


_SITE_PARSERS = {
    "tekkashop.com.vn": _tekkashop,
    "noithathoaphat.com.vn": _hoa_phat,
    "noithathunter.com": _hunter,
    "www.noithatlinco.com": _linco,
    "giakedehangpro.com": _gia_ke_pro,
    "hoaphathcm.vn": _hoaphathcm,
}


def extract_offer(url: str, page: str) -> dict:
    """Gia ban hien tai + gia goc cua SAN PHAM CHINH tren trang."""
    parser = _SITE_PARSERS.get(urlparse(url).netloc)
    offer = parser(page) if parser else _offer(None)
    if offer["status"] == "not_found":
        offer = _json_ld(page)
    if offer["status"] == "not_found" and re.search(r"Giá tham khảo\s*(?:<[^>]+>\s*)*Liên hệ",
                                                     page):
        offer = _offer(None, status="contact")
    return offer


# Nhan tiep theo sau "Chat lieu:" - doan chat lieu dung truoc nhan nay
_NEXT_LABELS = (
    "Màu sắc", "Màu Sắc", "Kích thước", "Kích Thước", "Xuất xứ", "Xuất Xứ", "Bảo hành",
    "Quy cách", "Tải trọng", "Thương hiệu", "Kiểu dáng", "Tính năng", "Công dụng",
    "Mã sản phẩm", "Model", "Trọng lượng", "Đóng gói", "Bề mặt", "Ứng dụng", "Loại hàng",
)
_MATERIAL = re.compile(r"(?:Chất liệu(?: sản phẩm| chính)?\s*:|Vật liệu\s*:?)\s*",
                       re.IGNORECASE)
# Trang khong co nhan, chi viet trong cau: "... duoc lam tu chat lieu sat cao cap, ..."
_MATERIAL_SENTENCE = re.compile(r"(?:làm|chế tạo|sản xuất) từ chất liệu\s+", re.IGNORECASE)


def extract_material(page: str) -> str | None:
    """Doan van sau nhan 'Chat lieu:' tren trang, cat o nhan ke tiep hoac cuoi cau."""
    text = _text(page)
    # Duyet moi lan xuat hien: lan dau co the la tieu de cot bang (Xuan Hoa: "Vat lieu
    # Loai hang ..."), gia tri that nam o lan sau
    for pattern in (_MATERIAL, _MATERIAL_SENTENCE):
        for match in pattern.finditer(text):
            value = text[match.end():match.end() + 300]
            cut = min([i for label in _NEXT_LABELS if (i := value.find(label)) >= 0] + [160])
            value = re.split(r"(?<=[a-zà-ỹ])\.\s|;|\s\|\s", value[:cut])[0]
            value = value.strip(" .,:-")
            if value:
                return value
    return None


_WARRANTY = re.compile(r"bảo hành(?:\s+chính hãng)?\s*:?\s*(\d{1,3})\s*(tháng|năm|ngày)",
                       re.IGNORECASE)
_TO_MONTHS = {"tháng": 1, "năm": 12}


def extract_warranty_months(page: str) -> int | None:
    """So thang bao hanh ghi ro tren trang; khong co thoi han cu the thi None."""
    match = _WARRANTY.search(_text(page))
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2).lower()
    if unit == "ngày":
        return round(value / 30.4)
    return value * _TO_MONTHS[unit]


# Thu tu uu tien theo loai san pham: vat lieu quyet dinh trai nghiem dung truoc.
# Khong co tu khoa chung chung ("go", "nem", "da"): "chan go", "mat ngoi bang nem",
# "boc da" khong du de ket luan chat lieu, nen de None thay vi doan.
_MATERIAL_KEYWORDS = {
    "da_that": ("da thật", "da bò"),
    "da_cong_nghiep": ("da pu", "giả da", "da công nghiệp", "simili", "pvc"),
    "luoi_nhua": ("lưới",),
    "vai_boc": ("vải", "nỉ"),
    "go_cao_su": ("gỗ cao su",),
    "go_tu_nhien": ("gỗ tự nhiên", "gỗ sồi", "gỗ óc chó", "gỗ thông"),
    "go_cong_nghiep": ("gỗ công nghiệp", "mfc", "mdf", "melamine", "laminate", "gỗ ép",
                       "mặt gỗ", "mặt bàn gỗ"),
    "nhua": ("nhựa",),
    "kim_loai": ("sắt", "thép", "kim loại", "inox"),
}
_PRIORITY = {
    "ghế văn phòng": ("da_that", "da_cong_nghiep", "luoi_nhua", "vai_boc", "nhua",
                      "go_tu_nhien", "go_cao_su", "go_cong_nghiep", "kim_loai"),
    # Sofa: chi xet chat lieu boc - mo ta khung go khong phai chat lieu cua sofa
    "sofa": ("da_that", "da_cong_nghiep", "vai_boc"),
    "bàn làm việc": ("go_tu_nhien", "go_cao_su", "go_cong_nghiep", "kim_loai"),
    "tủ hồ sơ": ("go_tu_nhien", "go_cao_su", "go_cong_nghiep", "kim_loai"),
    "kệ": ("go_tu_nhien", "go_cao_su", "go_cong_nghiep", "kim_loai"),
}


def normalize_material(raw: str | None, product_type: str) -> str | None:
    """Doan chat lieu tu do -> nhan cua dataset (vd 'kim_loai'); khong ro thi None."""
    if not raw:
        return None
    text = raw.lower()
    for label in _PRIORITY.get(product_type, tuple(_MATERIAL_KEYWORDS)):
        if any(keyword in text for keyword in _MATERIAL_KEYWORDS[label]):
            return label
    return None


_VARIANT_GROUP = re.compile(
    r'data-group="([^"]+)"><div class="hp-variation-label">[^<]*</div>'
    r'<div class="hp-variation-pills">(.*?)</div></div>', re.S)
_VARIANT_PILL = re.compile(
    r'<span class="hp-variation-pill( active)?" data-optionid="(\d+)">([^<]+)</span>')


def hoa_phat_variant_combos(page: str) -> tuple[str | None, list[dict]]:
    """Moi to hop bien the (vd 'Ghe 3 cho + Boc PVC') cua trang Hoa Phat.

    Gia HTML tinh chi la gia cua mot to hop; gia tung to hop phai lay qua
    hp_variation_price.php?productid=...&options=<option_ids>.
    """
    found = re.search(r'id="hpVariations" data-productid="(\d+)"', page)
    if not found:
        return None, []
    groups = [_VARIANT_PILL.findall(body) for _, body in _VARIANT_GROUP.findall(page)]
    combos = []
    for picked in itertools.product(*groups):
        combos.append({
            "label": " + ".join(label.strip() for _, _, label in picked),
            "option_ids": ",".join(option_id for _, option_id, _ in picked),
            "default": all(active for active, _, _ in picked),
        })
    return found.group(1), combos


def compare_row(row: dict, offer: dict) -> str:
    """So gia trong CSV nguon voi gia doc duoc tren trang."""
    status = offer.get("status", "")
    if status.startswith("http_"):
        return "dead_link"
    if status == "ambiguous":
        return "ambiguous_variants"
    csv_price = int(row["price"]) if str(row.get("price") or "").strip() else None
    if csv_price is None and offer.get("price") is None:
        return "ok"
    if offer.get("price") is None:
        return "price_not_found"
    return "ok" if csv_price == offer["price"] else "price_mismatch"
