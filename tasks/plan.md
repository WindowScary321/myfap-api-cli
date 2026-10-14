# Kế hoạch chuyển quy trình dev sang uv

## Phạm vi

Quản lý môi trường dev và dependencies bằng uv; sửa `myfap version` để đọc metadata của package `myfap`. Giữ setuptools, tên package và phạm vi Python >=3.9. Bump phiên bản lên 0.1.8 cho thay đổi này.

## Thứ tự thực hiện

1. Chọn Python 3.11 cho dev, tạo `uv.lock` và hướng dẫn README. Xác nhận `uv sync --locked` cài được package ở chế độ editable.
2. Thêm regression test qua lệnh CLI `version`, xác nhận test thất bại trước khi sửa tên distribution và thành công sau khi sửa.
3. Chuyển build CI sang uv, chạy test trên PR và giữ Trusted Publishing khi có release. Kiểm tra wheel và source distribution.
4. Review diff, kiểm tra tiếng Việt, tạo hai commit theo phạm vi và mở PR mới kèm bình luận kết quả kiểm tra.

## Rủi ro và cách kiểm tra

- Dependencies hiện chỉ có giới hạn phiên bản tối thiểu: lockfile cố định các phiên bản đã resolve; kiểm tra cài đặt và CLI trên Python 3.9/3.11.
- `greenlet` 3.2.5 thiếu wheel Python 3.9 trên Windows: giới hạn phiên bản qua cấu hình uv cho đúng môi trường này để tránh yêu cầu compiler C++.
- Playwright cần browser riêng khi đăng nhập: ghi rõ Chrome/Edge và Firefox dự phòng trong README; test version không đăng nhập hay gọi API.
- Môi trường dev và package phát hành khác nhau: kiểm tra `myfap version` cả sau editable install và sau cài wheel.

Danh sách công việc và trạng thái nằm trong [todo.md](todo.md).
