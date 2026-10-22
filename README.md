# Auto Fill Timesheet

Tự động đăng nhập vào hệ thống timesheet và điền các khung giờ làm việc
trong những ngày làm việc từ thứ Hai đến thứ Sáu. Chương trình bỏ qua các
entry đã tồn tại để tránh tạo trùng.

## Yêu cầu

- Python 3.11 trở lên
- Google Chrome hoặc Microsoft Edge
- WebDriver tương ứng được Selenium tự động quản lý
- Tài khoản hợp lệ trên hệ thống timesheet

## Cài đặt

1. Clone repository:

   ```bash
   git clone <repository-url>
   cd auto-fill-timesheet
   ```

2. Tạo file cấu hình cá nhân từ file mẫu:

   ```bash
   copy account.example.json account.json
   ```

   Trên macOS/Linux, dùng:

   ```bash
   cp account.example.json account.json
   ```

3. Mở `account.json` và điền `username`, `password`, khoảng ngày và các
   khung giờ cần nhập.

> **Bảo mật:** Không commit hoặc chia sẻ `account.json`. File này đã được
> thêm vào `.gitignore`; chỉ `account.example.json` với thông tin mẫu được
> lưu trong repository. Nếu `account.json` đã từng được commit trước đó,
> hãy xóa khỏi Git index bằng lệnh `git rm --cached account.json` và đổi
> mật khẩu tài khoản.

## Chạy chương trình

```bash
python main.py
```

Lần chạy đầu tiên, chương trình sẽ tự tạo môi trường `.venv` và cài
dependency trong `requirements.txt`. Sau đó Selenium sẽ mở trình duyệt,
đăng nhập và điền timesheet theo cấu hình.

## Cấu hình

| Trường | Mô tả |
| --- | --- |
| `driver` | Trình duyệt: `chrome` hoặc `edge` |
| `url` | Địa chỉ hệ thống timesheet |
| `username` | Tên đăng nhập cá nhân |
| `password` | Mật khẩu cá nhân |
| `time_sleep_duration` | Số giây chờ giữa các thao tác |
| `start_day`, `end_day` | Khoảng ngày, định dạng `DD.MM.YYYY` |
| `start_time_morning`, `end_time_morning` | Giờ bắt đầu/kết thúc buổi sáng |
| `start_time_afternoon`, `end_time_afternoon` | Giờ bắt đầu/kết thúc buổi chiều |

## Lưu ý

- Kiểm tra kỹ ngày và giờ trước khi chạy.
- Không sử dụng chương trình nếu không có quyền truy cập hệ thống.
- Nên kiểm tra lại dữ liệu trên hệ thống sau khi chương trình hoàn tất.
