# Phiếu thu 3 báo giá B2B — Người B

Trạng thái: chờ liên hệ và phản hồi thực tế; không được tự tạo số liệu.

## Quy tắc

- Thu ba báo giá cho 1–2 mặt hàng đã có giá web để so sánh được.
- Không commit số điện thoại, email cá nhân hoặc tên người liên hệ.
- Ghi rõ ngày báo giá, số lượng hỏi, giá/đơn vị, MOQ, thời gian giao, bảo hành.
- Field nhà cung cấp không trả lời phải để trống/null, không suy diễn.
- Chỉ đánh dấu `nguon_type=b2b_quote` khi có báo giá thật; bằng chứng gốc có
  thông tin cá nhân lưu ngoài repository.

## Ba dòng cần thu

| # | supplier_name | product_name | quote_date | quantity | unit_price_vnd | MOQ | delivery_days | warranty_months | public_source_url | trạng thái |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | | | | | | | | | | Chưa có |
| 2 | | | | | | | | | | Chưa có |
| 3 | | | | | | | | | | Chưa có |

Sau khi có dữ liệu, gửi C để nạp vào `src/tools/mock_data/sources/` theo schema
chung và gắn `simulated_fields` cho mọi trường không được báo giá xác nhận.
