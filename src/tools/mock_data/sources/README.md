# Du lieu nguon that

Tat ca du lieu nguon nam trong mot file duy nhat: `c_sourced_products.csv` (nguoi thu: C).
Cac file nhom theo A/B tung dung tam (`ghe_van_phong.csv`, `ban_lam_viec.csv`, `tu_ho_so.csv`,
`ke.csv`, `sofa.csv`) da bi xoa vi chi co header, khong co du lieu.

Moi dong la **mot san pham cu the tren mot trang ban hang that**. `generate_mock_data.py`
doc moi file `*.csv` o day, kiem tra hop le roi sinh ban ghi `SRC###` trong `suppliers.json`.

## Cot

| Cot | Bat buoc | Quy tac |
|---|---|---|
| `supplier_name` | co | ten cong ty nhu tren trang, khong dau, vi du `Noi That Linco` |
| `product_type` | co | dung mot trong: `ghế văn phòng`, `bàn làm việc`, `tủ hồ sơ`, `kệ`, `sofa` |
| `product_name` | co | ten san pham nhu tren trang |
| `price` | cot co, gia tri duoc trong | VND viet lien, vi du `9400000`. Trang ghi "Lien he" thi **de trong**, khong doan |
| `unit` | co | `cai`, `bo`... |
| `region` | co | `Ha Noi`, `TP.HCM` hoac `Da Nang` - theo dia chi showroom/chi nhanh ghi tren trang. Khong ro thi bo dong |
| `source_url` | co | link trang **san pham** (khong phai trang chu), moi link chi dung cho mot dong |
| `collected_at` | co | ngay mo trang, `YYYY-MM-DD` |
| `collected_by` | co | `A`, `B`, `C`; dong do script crawl ma chua duyet thi ghi `C(script)` |
| `material` | khong | vi du `vai_boc`, `da_that`, `go_cong_nghiep`, `kim_loai`, `luoi_nhua` |
| `moq`, `stock`, `delivery_days` | khong | chi dien khi trang ghi ro. Trong thi generator mo phong va danh dau trong `simulated_fields` |
| `warranty_months`, `trust_score` | khong | chi dien khi trang ghi ro. Trong thi de `null`, khong mo phong |
| `note` | khong | ghi chu cho nguoi duyet, khong dua vao du lieu |

## Kiem tra truoc khi gui

```bash
python generate_mock_data.py
python -m unittest tests.test_dataset_builder tests.test_dataset_files -v
```

Neu generator bao `Du lieu nguon khong hop le`, moi dong loi co dang `ten_file:so_dong: mo ta`.
Sua dung dong do roi chay lai.
