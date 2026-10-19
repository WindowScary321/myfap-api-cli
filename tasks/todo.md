# Công việc chuyển sang uv

- [x] Thiết lập `.python-version`, tạo `uv.lock`, cập nhật README; `uv sync --locked` thành công.
- [x] Thêm regression test và sửa `myfap version`; xác nhận test thất bại trước sửa và thành công sau sửa.
- [x] Cập nhật CI/build, kiểm tra local trên Python 3.9/3.11 và cài wheel trong môi trường riêng.
- [x] Review diff và kiểm tra tiếng Việt; sẵn sàng tạo commit, PR và bình luận bằng tiếng Việt.

Kết quả GitHub Actions và bình luận kiểm tra được theo dõi trực tiếp trong PR. Đăng nhập và gọi API đã được kiểm chứng theo từng phase; các mục live còn mở được liệt kê bên dưới. Publish PyPI vẫn thuộc Phase 5.

## Kiểm chứng live còn mở trước khi phát hành

- [x] Chạy lại `news`, `other notification` và `other fee` trên v1/APHL bằng session tạm ngày 19/10/2026. News/notification nhận HTTP 200/body 201; fee nhận HTTP 404. Lệnh đối chứng `info student` đạt 200/200 trước và sau; session/lock tạm đã xóa. Xem [báo cáo live v1](../docs/phase4-coverage.md#chạy-lại-ba-lệnh-v1-ngày-19102026).
- [ ] Xác minh ý nghĩa body 201 của `news` v1 và đối chiếu trường hợp có dữ liệu. Lượt live mới vẫn có `data: null`, message null hoặc không có. Không gộp mọi code 201 vào hết phiên hoặc coi đó là danh sách rỗng hợp lệ.
- [ ] Xác định nguyên nhân body 201 của `other notification` v1. Request khớp path/query/checksum của app; session đối chứng vẫn đọc được, chưa xác nhận lỗi thuộc backend hay điều kiện tài khoản.
- [ ] Xác nhận `GeFeeByRoll` v1 có response thành công hoặc có bằng chứng từ đơn vị vận hành về phạm vi hỗ trợ. HTTP 404 trên APHL chưa đủ để kết luận route đã ngừng hỗ trợ trên mọi campus hoặc suy ra schema.
- [ ] Kiểm chứng positive case cho fee bằng tài khoản có khoản học phí cần thanh toán hoặc dữ liệu hóa đơn phù hợp; đối chiếu `IsPaid`, số tiền và thông tin hóa đơn trên payload thật. HTTP/body 200 với dữ liệu rỗng chưa đủ để đóng mục này.
- [ ] Kiểm chứng positive case cho survey bằng tài khoản có khảo sát bắt buộc; đối chiếu payload có dữ liệu với contract của dịch vụ survey. Trạng thái `Data Not Found` chưa đủ để đóng mục này.

Mỗi mục cần session tạm, kết quả ghi rõ API version/campus và metadata đã lọc trước khi đóng. Không đưa credential, thông tin cá nhân hoặc raw response lên Git. CI xanh, fixture hoặc kết quả API v2 không thay thế kiểm chứng live v1. Xem [checklist Phase 4](phase4.md) và [báo cáo coverage](../docs/phase4-coverage.md).
