# Auto Fill Timesheet

Tự động đăng nhập vào hệ thống timesheet và điền các khung giờ làm việc
trong những ngày làm việc từ thứ Hai đến thứ Sáu, bỏ qua các ngày nghỉ lễ
khai báo trong mảng `holidays`. Chương trình bỏ qua các
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

## Giao diện cấu hình

Mở như một app bằng một trong các cách:

- Bấm đúp file **`Auto Fill Timesheet.bat`** trong thư mục project.
- Hoặc chạy `python config_ui.py`.
- Tạo shortcut ngoài Desktop: chuột phải `Auto Fill Timesheet.bat` →
  *Send to* → *Desktop (create shortcut)*.

Cửa sổ cấu hình cho phép sửa toàn bộ `account.json`, nhập ngày nghỉ lễ
(mỗi dòng một ngày) và chọn **Project / Activity** từ danh sách thả xuống:

1. Bấm **Tải danh sách project/activity từ hệ thống**: chương trình đăng
   nhập, đọc tất cả project và activity tương ứng của từng project, lưu vào
   `options.json`.
2. Chọn project, danh sách activity sẽ đổi theo project đó.
3. Bấm **Lưu** hoặc **Lưu & chạy**.

Có thể lấy danh sách bằng dòng lệnh: `python main.py --fetch-options`.

### Xóa entry theo ngày

Nhập các ngày vào ô **Ngày cần xóa** (mỗi dòng một ngày `DD.MM.YYYY` hoặc
một khoảng `DD.MM.YYYY-DD.MM.YYYY`) rồi bấm **Xóa toàn bộ entry của các ngày
này**. Với mỗi entry của ngày đó, chương trình mở hộp thoại sửa, tích
**Erase Entry** và bấm OK. Chỉ xóa được các entry đang hiển thị trong danh
sách trên trang.

Dòng lệnh: `python main.py --delete 20.11.2026 23.11.2026-25.11.2026`.

## Cấu hình

| Trường | Mô tả |
| --- | --- |
| `driver` | Trình duyệt: `chrome` hoặc `edge` |
| `url` | Địa chỉ hệ thống timesheet |
| `username` | Tên đăng nhập cá nhân |
| `password` | Mật khẩu cá nhân |
| `time_sleep_duration` | Thời gian chờ **tối đa** cho mỗi bước (giây, tối thiểu 10). Trang tải xong sớm thì chương trình làm tiếp ngay |
| `start_day`, `end_day` | Khoảng ngày, định dạng `DD.MM.YYYY` |
| `start_time_morning`, `end_time_morning` | Giờ bắt đầu/kết thúc buổi sáng |
| `start_time_afternoon`, `end_time_afternoon` | Giờ bắt đầu/kết thúc buổi chiều |
| `project` | (Tùy chọn) Tên project đúng như hiển thị trên hệ thống. Để trống = chọn project đầu tiên như trước |
| `activity` | (Tùy chọn) Tên activity của project đó. Để trống = chọn activity mặc định như trước |
| `holidays` | (Tùy chọn) Mảng các ngày nghỉ lễ sẽ không điền, định dạng `DD.MM.YYYY`, ví dụ `["01.01.2026", "02.09.2026"]` |

## Lưu ý

- Kiểm tra kỹ ngày và giờ trước khi chạy.
- Không sử dụng chương trình nếu không có quyền truy cập hệ thống.
- Nên kiểm tra lại dữ liệu trên hệ thống sau khi chương trình hoàn tất.

## Đóng gói thành app (không cần cài Python)

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Kết quả là `release\AutoFillTimesheet.zip`. Người dùng chỉ cần giải nén và
bấm đúp `AutoFillTimesheet.exe`. Gói chỉ chứa `account.json` mẫu (lấy từ
`account.example.json`), không chứa thông tin đăng nhập cá nhân. Hướng dẫn
cho người dùng nằm trong `HUONG_DAN.txt`.
