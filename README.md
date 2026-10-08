# auto fill timesheet
# cấu hình account.json trước khi chạy
# chỉ cần ấn Run trên VSCODE or IDE khác để chạy file main.py

`project_name` và `activity_name` là tùy chọn nhưng nên khai báo cho từng tài khoản.
Code sẽ chọn theo tên hoặc value thay vì phụ thuộc vào thứ tự option, vì mỗi tài
khoản có thể được cấp danh sách project/activity khác nhau.

Ví dụ:

```json
{
    "project_name": "Tên project trên trang",
    "activity_name": "Tên activity trên trang"
}
```

Nếu không khai báo, chương trình vẫn dùng project đầu tiên và activity thứ 10
như cách cũ. Nếu tài khoản không có option tương ứng, chương trình sẽ dừng và
in danh sách option hiện có để cấu hình lại.
