# Thiết lập Rơle từ tập lệnh này tới Telegram Bot

## Bước 1: Tạo Bot Telegram bằng BotFather

1. **Tìm kiếm BotFather**trong ứng dụng khách Telegram của bạn hoặc sử dụng liên kết này: [BotFather](https://t.me/botfather).

2. **Tạo Bot mới**:
   -Bắt đầu trò chuyện với BotFather.
   -Nhập lệnh `/newbot`.
   -Làm theo hướng dẫn để đặt tên cho bot của bạn và đặt tên người dùng duy nhất cho nó.
   -**Sao chép mã thông báo**do BotFather cung cấp. Mã thông báo này sẽ được sử dụng để truy cập API HTTP cho bot của bạn. **Giữ mã thông báo này an toàn**, vì bất kỳ ai có quyền truy cập vào nó đều có thể điều khiển bot của bạn.

3. **Gửi tin nhắn tới Bot mới của bạn**:
   -Truy cập URL bot của bạn do BotFather cung cấp, URL này sẽ có dạng như `https://t.me/myBotName_bot`.
   -Gõ "Xin chào" và nhấn enter để gửi tin nhắn. Điều này sẽ khởi tạo một cuộc trò chuyện mà tập lệnh của chúng tôi sẽ sử dụng.

## Bước 2: Cấu hình Script sử dụng Telegram Bot
4. **Khởi chạy bất kỳ trò chơi nào và chọn `y` để chỉnh sửa cài đặt**:
   -Ví dụ chạy `./launch.sh hot`.
   -Cuộn qua các tùy chọn bằng cách nhấn Enter cho đến khi bạn đạt đến tùy chọn "Mức độ chi tiết của Telegram".
   -Chọn mức độ chi tiết từ 0 (không đẩy cập nhật) đến 3 (đẩy từng bước nhỏ). Đối với hầu hết người dùng, cấp 1 là một lựa chọn tốt.
   -Tiếp tục kéo xuống cho đến khi đến phần "Nhập Telegram Bot Token" và nhập access token từ BotFather.
   -Tiếp tục nhấn Enter cho đến khi tất cả các cài đặt đã được duyệt qua và các cài đặt đã sửa đổi được hiển thị.
   -Tại thời điểm này, bạn có thể thiết lập phiên trò chơi mới hoặc nhấn Ctrl+C để thoát.
   -Sau khi hoàn tất các bước này, mỗi phiên trò chơi được khởi động lại với cài đặt cập nhật sẽ đẩy các bản cập nhật lên bot của bạn.

5. **Thiết lập tương tác bổ sung với Bot Telegram của bạn**:
   -Chạy `./launch.sh tg-bot` để thêm mức độ tương tác bổ sung giữa các phiên trò chơi của bạn và bot Telegram.
   -Tập lệnh này sẽ thiết lập quy trình PM2 để theo dõi các yêu cầu từ bạn trong Telegram.
   -Sau khi thiết lập, bạn có thể sử dụng các lệnh như `/start`, `/help`, `/status`, `/logs`, và `/exit` để lấy thêm thông tin cho mỗi phiên trò chơi bằng cách chọn các liên kết từ danh sách của các lựa chọn.

Bằng cách làm theo các bước này, bạn sẽ có một chuyển tiếp được định cấu hình đầy đủ từ tập lệnh đến bot Telegram, cho phép bạn nhận thông tin cập nhật và tương tác với các phiên trò chơi của mình thông qua Telegram.
