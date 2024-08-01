## Hướng dẫn Windows Thiết lập Ubuntu 24.04 với WSL2

Hướng dẫn này sẽ giúp bạn thiết lập Ubuntu 24.04 trên PC Windows bằng Hệ thống con Windows cho Linux 2 (WSL2). Thiết lập này cho phép bạn chạy bản phân phối Linux nguyên bản trên máy Windows của mình.

### Điều kiện tiên quyết

Trước khi bắt đầu, hãy đảm bảo rằng phiên bản Windows của bạn hỗ trợ WSL2. Bạn cần Windows 10, phiên bản 2004, Build 19041 trở lên hoặc Windows 11.

### Hướng dẫn từng bước một

1. **Tải xuống Ubuntu 24.04**
Tải xuống [Ubuntu 24.04](https://www.microsoft.com/store/productId/9NZ3KLHXDJP5) từ Microsoft Store.
2. **Bật WSL2**

   Mở PowerShell với tư cách **Quản trị viên**và bật WSL2 bằng các lệnh sau:

   ```powershell
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   ```
### Đặt WSL2 làm phiên bản mặc định:

   ```powershell
   wsl --set-default-version 2
   ```
Khởi động lại máy tính của bạn và mở ứng dụng Ubuntu 24.04 trước khi làm theo hướng dẫn Ubuntu bên dưới.

### Tùy chọn: Định cấu hình PM2 để khởi động lại sau khi khởi động lại

Để khởi động lại PM2 sau khi khởi động lại, bạn có thể thiết lập tập lệnh khởi động:

1. Mở hộp thoại Run bằng cách nhấn `Win + R`, gõ `shell:startup` và nhấn Enter.
2. Sao chép tệp `windows_pm2_restart.bat` từ thư mục kho lưu trữ GitHub vào thư mục khởi động Windows của bạn.
   
Tập lệnh này đảm bảo rằng PM2 tự động khởi động lại sau khi khởi động lại hệ thống. Để biết thêm chi tiết, hãy tham khảo video hướng dẫn được liên kết bên dưới.

### Tài nguyên bổ sung

Để có hướng dẫn chi tiết hơn, hãy xem xét xem các video hướng dẫn sau:

-[Thiết lập và cấu hình WSL2](#)
-[Sử dụng PM2 với WSL2](#)

Bằng cách làm theo các bước này, bạn sẽ có môi trường Ubuntu 24.04 đầy đủ chức năng chạy trên WSL2, cho phép bạn tận dụng các công cụ và quy trình công việc Linux trực tiếp từ PC Windows của mình.