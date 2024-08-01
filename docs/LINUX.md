## Cài đặt Linux độc lập (Ubuntu 20.04 đến 24.04):

Đảm bảo Hệ điều hành của bạn được cập nhật bằng cách chạy các lệnh sau:
``` bash
   sudo apt-get update
   sudo apt-get upgrade -y
   sudo reboot
```

Thực thi khối lệnh QuickStart để sao chép kho lưu trữ GitHub này, thiết lập Môi trường ảo và cài đặt tất cả các phần phụ thuộc:
```bash
   sudo apt install -y git
   git clone https://github.com/bibo318/game-telegram-autobot.git
   cd game-telegram-autobot
   sudo chmod +x install.sh launch.sh
   ./install.sh
```

**Chỉ người dùng Ubuntu:**Cho phép PM2 tiếp tục khởi động lại bằng lệnh sau (người dùng Windows làm theo Hướng dẫn Windows).
```bash
   pm2 startup systemd
```

Nếu bạn không có quyền root, bạn hãy xem đầu ra PM2 để biết lời nhắc chạy với tư cách root. Một ví dụ có thể là:

```sudo env PATH=$PATH:/usr/bin /usr/lib/node_modules/pm2/bin/pm2 startup systemd -u ubuntu --hp /home/ubuntu```

Bằng cách làm theo các bước này, bạn sẽ có một môi trường đầy đủ chức năng để chạy Telegram Claim Bot trên hệ thống Ubuntu của mình. Đảm bảo kiểm tra tệp [DOCKER.md](docs/DOCKER.md) để biết hướng dẫn chi tiết về cách sử dụng Docker nếu muốn.