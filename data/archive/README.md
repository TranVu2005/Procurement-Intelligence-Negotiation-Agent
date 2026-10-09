# Dữ liệu tham chiếu legacy

`real_data_ghe_ban.json` được giữ nguyên từ phiên bản trước để bảo toàn dữ liệu nguồn/tham chiếu. File dùng mã NCC và schema cũ, không được runtime hoặc generator hiện hành đọc.

Nguồn hiện hành ở `src/tools/mock_data/sources/`; dataset runtime là `src/tools/mock_data/suppliers.json`, đi kèm VERSION. Không nhập trực tiếp file legacy vào dataset mới khi chưa kiểm tra schema và provenance.
