"""Doi chieu gia/chat lieu/bao hanh voi trang san pham that (src/tools/source_verify.py)."""

import unittest

from src.tools.source_verify import (
    compare_row,
    extract_material,
    extract_offer,
    extract_warranty_months,
    hoa_phat_variant_combos,
    normalize_material,
    parse_vnd,
)


class ParseVndTests(unittest.TestCase):
    def test_formats_seen_on_the_supplier_sites(self) -> None:
        self.assertEqual(parse_vnd("1,927,000vnđ"), 1927000)
        self.assertEqual(parse_vnd("450.000₫"), 450000)
        self.assertEqual(parse_vnd("11,400,000.00 ₫"), 11400000)
        self.assertEqual(parse_vnd("750.000 VNĐ"), 750000)

    def test_text_without_a_price_is_none(self) -> None:
        self.assertIsNone(parse_vnd("Liên hệ"))
        self.assertIsNone(parse_vnd(""))


class ExtractOfferTests(unittest.TestCase):
    def test_tekkashop_reads_the_embedded_variant_json_in_hundredths(self) -> None:
        page = ('<div data-p="{&quot;x&quot;:1}"></div> "variants": [{&quot;id&quot;:1,'
                '&quot;title&quot;:&quot;Default Title&quot;,&quot;price&quot;:117000000,'
                '&quot;compare_at_price&quot;:195000000}]')
        offer = extract_offer("https://tekkashop.com.vn/products/a", page)
        self.assertEqual(offer["price"], 1170000)
        self.assertEqual(offer["regular_price"], 1950000)
        self.assertEqual(offer["status"], "ok")

    def test_tekkashop_variants_with_different_prices_are_ambiguous(self) -> None:
        page = ('"variants": [{&quot;title&quot;:&quot;Den&quot;,&quot;price&quot;:100000000,'
                '&quot;compare_at_price&quot;:null},{&quot;title&quot;:&quot;Trang&quot;,'
                '&quot;price&quot;:120000000,&quot;compare_at_price&quot;:null}]')
        offer = extract_offer("https://tekkashop.com.vn/products/a", page)
        self.assertEqual(offer["status"], "ambiguous")
        self.assertEqual(sorted(offer["variant_prices"]), [1000000, 1200000])

    def test_hoa_phat_reads_the_main_price_block(self) -> None:
        page = '<div class="hp-product-price" style=""> 1,927,000vnđ </div><div class="price">845,300vnđ</div>'
        offer = extract_offer("https://noithathoaphat.com.vn/products/x.html", page)
        self.assertEqual(offer["price"], 1927000)

    def test_hunter_on_sale_takes_the_second_number_as_the_price(self) -> None:
        page = ('<p class="price product-page-price price-on-sale"><del>265,000 ₫</del>'
                '<ins>240,000 ₫</ins></p><div class="quantity">')
        offer = extract_offer("https://noithathunter.com/san-pham/x/", page)
        self.assertEqual(offer["price"], 240000)
        self.assertEqual(offer["regular_price"], 265000)

    def test_hunter_without_sale_has_one_price(self) -> None:
        page = '<p class="price product-page-price "> 220,000 ₫ </p><div class="quantity">'
        offer = extract_offer("https://noithathunter.com/san-pham/x/", page)
        self.assertEqual(offer["price"], 220000)
        self.assertIsNone(offer["regular_price"])

    def test_linco_reads_discounted_and_compare_price(self) -> None:
        page = ('"formattedPrice":"7.500.000₫","formattedComparePrice":"9.000.000₫",'
                '"formattedDiscountedPrice":"7.200.000₫"')
        offer = extract_offer("https://www.noithatlinco.com/product-page/x", page)
        self.assertEqual(offer["price"], 7200000)
        self.assertEqual(offer["regular_price"], 9000000)

    def test_gia_ke_pro_reads_special_and_old_price(self) -> None:
        page = ('<div class="special-price"><span class="price">450.000₫</span></div>'
                '<div class="old-price"><del class="price-old">530.000₫</del></div>')
        offer = extract_offer("https://giakedehangpro.com/x", page)
        self.assertEqual(offer["price"], 450000)
        self.assertEqual(offer["regular_price"], 530000)

    def test_hoaphathcm_reads_the_detail_price(self) -> None:
        page = '<div class="price-new-pro-detail">750.000 VNĐ</div>'
        offer = extract_offer("https://hoaphathcm.vn/x", page)
        self.assertEqual(offer["price"], 750000)

    def test_contact_for_price_is_not_a_number(self) -> None:
        page = '<div class="price ms-xl-5"> Giá tham khảo Liên hệ </div>'
        offer = extract_offer("https://xuanhoa.vn/x", page)
        self.assertIsNone(offer["price"])
        self.assertEqual(offer["status"], "contact")

    def test_json_ld_is_the_fallback_for_other_sites(self) -> None:
        page = ('<script type="application/ld+json">{"@type":"Product","offers":'
                '{"@type":"Offer","price": "899999","priceCurrency":"VND"}}</script>')
        offer = extract_offer("https://kesatngoctin.com/x", page)
        self.assertEqual(offer["price"], 899999)

    def test_page_without_any_price_is_not_found(self) -> None:
        offer = extract_offer("https://kesatngoctin.com/x", "<html>khong co gi</html>")
        self.assertEqual(offer["status"], "not_found")


class MaterialAndWarrantyTests(unittest.TestCase):
    def test_material_is_the_text_after_the_label_until_the_next_label(self) -> None:
        page = "<p>Chất liệu: Khung tựa nhựa, đệm mút bọc vải, chân nhựa đúc</p><p>Màu Sắc: Ghi</p>"
        self.assertEqual(extract_material(page), "Khung tựa nhựa, đệm mút bọc vải, chân nhựa đúc")

    def test_material_label_variants(self) -> None:
        page = "<li>Chất liệu sản phẩm: Tựa lưng nhựa PP, nệm ngồi bọc vải, chân thép sơn</li>"
        self.assertTrue(extract_material(page).startswith("Tựa lưng nhựa PP"))

    def test_no_material_label_is_none(self) -> None:
        self.assertIsNone(extract_material("<p>San pham dep</p>"))

    def test_warranty_units_are_converted_to_months(self) -> None:
        self.assertEqual(extract_warranty_months("Bảo hành chính hãng 12 tháng"), 12)
        self.assertEqual(extract_warranty_months("Bảo hành: 1 năm theo tiêu chuẩn"), 12)
        self.assertEqual(extract_warranty_months("bảo hành 365 Ngày"), 12)

    def test_warranty_policy_links_without_a_duration_are_ignored(self) -> None:
        self.assertIsNone(extract_warranty_months("Chính sách bảo hành đổi trả"))

    def test_material_is_normalized_to_the_dataset_labels(self) -> None:
        self.assertEqual(normalize_material("Kệ sắt sơn tĩnh điện cao cấp", "kệ"), "kim_loai")
        self.assertEqual(normalize_material("Lưng lưới, chân thép", "ghế văn phòng"), "luoi_nhua")
        self.assertEqual(normalize_material("Bọc da thật nhập khẩu", "sofa"), "da_that")
        self.assertEqual(normalize_material("Mặt gỗ MFC chống ẩm, chân sắt", "bàn làm việc"),
                         "go_cong_nghiep")
        self.assertIsNone(normalize_material("Chất liệu cao cấp, bền đẹp", "kệ"))

    def test_pu_leather_is_not_genuine_leather_nor_metal(self) -> None:
        self.assertEqual(normalize_material(
            "Da PU cao cấp bọc đệm mút, chân ghế thép mạ", "ghế văn phòng"), "da_cong_nghiep")

    def test_unspecified_leather_is_left_unknown(self) -> None:
        # Trang chi ghi "boc da", khong noi da that -> khong duoc gan da_that
        self.assertEqual(normalize_material("Khung chân thép mạ, đệm tựa bọc da",
                                            "ghế văn phòng"), "kim_loai")
        self.assertIsNone(normalize_material("đệm tựa bọc da", "sofa"))

    def test_plastic_shell_chair_with_wooden_legs_is_plastic(self) -> None:
        self.assertEqual(normalize_material(
            "đế và lưng đúc liền khối bằng nhựa Chân gỗ có gia cố bằng thép", "ghế văn phòng"),
            "nhua")

    def test_cushion_word_alone_is_not_fabric(self) -> None:
        self.assertEqual(normalize_material(
            "mặt ngồi bằng nệm, khung sắt sơn tĩnh điện", "ghế văn phòng"), "kim_loai")

    def test_sofa_frame_description_is_not_the_upholstery(self) -> None:
        self.assertIsNone(normalize_material(
            "Khung bằng gỗ chịu lực dày kết hợp với gỗ ván ép", "sofa"))

    def test_xuan_hoa_vat_lieu_skips_the_empty_table_header(self) -> None:
        page = ("<th>Kích thước (mm)</th><th>Vật liệu</th><th>Loại hàng</th> ... "
                "<td>Vật liệu</td><td>Thép sơn tĩnh điện,</td><td>Loại hàng</td><td>Hàng Đặt</td>")
        self.assertEqual(extract_material(page), "Thép sơn tĩnh điện")

    def test_material_stops_at_the_usage_label(self) -> None:
        page = "<p>Chất liệu: Thép sơn tĩnh điện Ứng dụng: Phù hợp cho kho hàng</p>"
        self.assertEqual(extract_material(page), "Thép sơn tĩnh điện")

    def test_material_written_in_a_sentence_is_found(self) -> None:
        page = "<p>Kệ NTKHSVP9092 được làm từ chất liệu sắt cao cấp, phủ sơn tĩnh điện.</p>"
        self.assertEqual(extract_material(page), "sắt cao cấp, phủ sơn tĩnh điện")


class HoaPhatVariantTests(unittest.TestCase):
    PAGE = ('<div class="hp-variations" id="hpVariations" data-productid="2380">'
            '<div class="hp-variation-group" data-group="Loại ghế SOFA">'
            '<div class="hp-variation-label">Loại ghế SOFA</div><div class="hp-variation-pills">'
            '<span class="hp-variation-pill active" data-optionid="377">Ghế 3 chỗ</span>'
            '<span class="hp-variation-pill" data-optionid="378">Ghế 4 chỗ</span></div></div>'
            '<div class="hp-variation-group" data-group="Chất liệu">'
            '<div class="hp-variation-label">Chất liệu</div><div class="hp-variation-pills">'
            '<span class="hp-variation-pill active" data-optionid="379">Bọc Da thật</span>'
            '<span class="hp-variation-pill" data-optionid="381">Bọc PVC</span></div></div></div>')

    def test_variant_groups_and_default_selection_are_read(self) -> None:
        product_id, combos = hoa_phat_variant_combos(self.PAGE)
        self.assertEqual(product_id, "2380")
        self.assertEqual(len(combos), 4)
        default = [c for c in combos if c["default"]]
        self.assertEqual(default[0]["label"], "Ghế 3 chỗ + Bọc Da thật")
        self.assertEqual(default[0]["option_ids"], "377,379")

    def test_page_without_variants_has_no_combos(self) -> None:
        self.assertEqual(hoa_phat_variant_combos("<div>khong co</div>"), (None, []))


class CompareRowTests(unittest.TestCase):
    def test_matching_price_is_ok(self) -> None:
        verdict = compare_row({"price": "1927000"}, {"price": 1927000, "status": "ok"})
        self.assertEqual(verdict, "ok")

    def test_different_price_is_a_mismatch(self) -> None:
        verdict = compare_row({"price": "1927000"}, {"price": 1637100, "status": "ok"})
        self.assertEqual(verdict, "price_mismatch")

    def test_empty_csv_price_and_contact_page_agree(self) -> None:
        self.assertEqual(compare_row({"price": ""}, {"price": None, "status": "contact"}), "ok")

    def test_dead_link_is_reported(self) -> None:
        self.assertEqual(compare_row({"price": "1"}, {"price": None, "status": "http_404"}),
                         "dead_link")


if __name__ == "__main__":
    unittest.main()
