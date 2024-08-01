# Thiết lập Docker cho Telegram Claim Bot (hiện tương thích X86 + ARM64)
Việc sử dụng Docker giúp đơn giản hóa việc thiết lập Telegram Claim Bot bằng cách chứa ứng dụng và các phần phụ thuộc của nó. Điều này đảm bảo một môi trường nhất quán trên các kiến ​​trúc khác nhau (X86/ARM64) và các hệ điều hành (dựa trên Linux/Windows), đồng thời loại bỏ các vấn đề liên quan đến quản lý phụ thuộc và xung đột phiên bản. Docker cũng cung cấp một cách dễ dàng để triển khai, mở rộng quy mô và quản lý ứng dụng, khiến nó trở thành lựa chọn lý tưởng để chạy Telegram Claim Bot một cách hiệu quả.

Để bắt đầu với Docker, bạn cần cài đặt Docker trên thiết bị của mình. Xem ví dụ cài đặt Linux cho Amazon Linux và Ubuntu bên dưới. Đối với máy Windows, bạn có thể tải xuống và cài đặt Docker Desktop từ [trang web chính thức của Docker](https://www.docker.com/products/docker-desktop/).

## Để thiết lập vùng chứa với tập lệnh và phần phụ thuộc:
```sh
docker run -d --name telegram-claim-bot --restart unless-stopped bibo318/telegram-claim-bot:latest
```
## Để tương tác với tập lệnh, bao gồm thêm tài khoản hoặc giám sát:
```sh
docker exec -it telegram-claim-bot /bin/bash
```
## Để thêm một trò chơi:
```sh
# Để chọn từ danh sách các tập lệnh có sẵn:
./launch.sh
# hoặc để chỉ định tập lệnh theo tên:
./launch.sh hot
```
## Để Cập Nhật Code Mới Nhất hoặc Game Mới:
```sh
./pull-games.sh
```
## Để xóa các tiến trình hoặc thư mục không mong muốn:
```sh
./remove-process.sh
```
## Để Xem Các Trò Chơi Đang Chạy (nếu có):
```sh
pm2 list
```
## Để xem kết quả từ trò chơi (để giám sát):
```sh
pm2 logs 
# hoặc cho nhật ký cụ thể
pm2 logs 1
# hoặc theo tên
pm2 logs HOT:Wallet1
```
## Để bắt đầu phiên sau khi khởi động lại hoặc dừng:
```sh
docker start telegram-claim-bot
docker exec -it telegram-claim-bot /bin/bash
```
## Để loại bỏ container:
```sh
docker stop telegram-claim-bot
docker rm telegram-claim-bot
```
Tất cả các hướng dẫn khác đều phù hợp với [README.md](https://github.com/bibo318/game-telegram-autobot) chính.

# Ví dụ về thiết lập Linux:

## Chỉ chạy lần đầu: Mở Terminal qua SSH và chạy các lệnh này.

### Bước 1 (Amazon Linux) -Cài đặt Docker và thêm người dùng hiện tại vào nhóm Docker:
```sh
sudo yum update -y
sudo yum install docker -y
sudo service docker start
sudo usermod -aG docker $USER
exit
```
### Bước 1 (Ubuntu) -Cài đặt Docker và thêm người dùng hiện tại vào nhóm Docker:
```sh
sudo apt-get update -y
sudo apt-get install docker.io -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
exit
```
### Bước 2 -Mở lại Terminal và khởi động Claim Bot
#### Lưu ý: `--restarttrừ khi-stopped` được đặt trong ví dụ này, để khởi động lại vùng chứa khi khởi động lại, v.v.
```sh
docker run -d --name telegram-claim-bot --restart unless-stopped bibo318/telegram-claim-bot:latest
```
### Bước 3 -Tương tác với Docker Container
To interact with the script, including adding accounts or monitoring, use:
```sh
docker exec -it telegram-claim-bot /bin/bash
```
### Để thoát Docker và quay lại Amazon Linux CLI:
Press `Ctrl + D` or type:
`exit`

### Làm theo hướng dẫn ở đầu trang để biết chi tiết về cách tương tác với tập lệnh.