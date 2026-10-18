# Công việc chuyển sang uv

- [x] Thiết lập `.python-version`, tạo `uv.lock`, cập nhật README; `uv sync --locked` thành công.
- [x] Thêm regression test và sửa `myfap version`; xác nhận test thất bại trước sửa và thành công sau sửa.
- [x] Cập nhật CI/build, kiểm tra local trên Python 3.9/3.11 và cài wheel trong môi trường riêng.
- [x] Review diff và kiểm tra tiếng Việt; sẵn sàng tạo commit, PR và bình luận bằng tiếng Việt.

Kết quả GitHub Actions và bình luận kiểm tra được theo dõi trực tiếp trong PR. Đăng nhập và gọi API đã được kiểm chứng theo từng phase; các mục live còn mở được liệt kê bên dưới. Publish PyPI vẫn thuộc Phase 5.

## Kiểm chứng live còn mở trước khi phát hành

- [ ] Chạy lại `news` v1 với session tạm của tài khoản được phép kiểm thử; xác minh ý nghĩa response `code: 201` đã quan sát và đối chiếu trường hợp có dữ liệu. Không gộp mọi code 201 vào hết phiên.
- [ ] Chạy lại `other notification` v1 với session tạm của tài khoản được phép kiểm thử; phân biệt dữ liệu rỗng với lỗi nghiệp vụ hoặc hết phiên, ghi lại HTTP/body code.
- [ ] Chạy lại `other fee` v1 và ghi nhận response thành công hoặc bằng chứng route không khả dụng; không suy ra schema từ HTTP 404.
- [ ] Kiểm chứng positive case cho fee bằng tài khoản có khoản học phí cần thanh toán hoặc dữ liệu hóa đơn phù hợp; đối chiếu `IsPaid`, số tiền và thông tin hóa đơn trên payload thật. HTTP/body 200 với dữ liệu rỗng chưa đủ để đóng mục này.
- [ ] Kiểm chứng positive case cho survey bằng tài khoản có khảo sát bắt buộc; đối chiếu payload có dữ liệu với contract của dịch vụ survey. Trạng thái `Data Not Found` chưa đủ để đóng mục này.

Mỗi mục cần session tạm, kết quả ghi rõ API version/campus và metadata đã lọc trước khi đóng. Không đưa credential, thông tin cá nhân hoặc raw response lên Git. CI xanh, fixture hoặc kết quả API v2 không thay thế kiểm chứng live v1. Xem [checklist Phase 4](phase4.md) và [báo cáo coverage](../docs/phase4-coverage.md).
