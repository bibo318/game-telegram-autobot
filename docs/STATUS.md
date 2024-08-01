# TÌNH TRẠNG.md

## Tổng quan

Tập lệnh này cho phép bạn quản lý và giám sát các quy trình PM2 của mình cho nhiều trò chơi khác nhau. Bạn có thể xem trạng thái của tất cả các tài khoản của mình, xóa các quy trình và xem tất cả nhật ký PM2 ở một nơi.

## Cách sử dụng
Để khởi chạy tập lệnh trạng thái, hãy chạy:
```
./launch.sh status
```

## Tùy chọn

### Sắp xếp theo thời gian yêu cầu tiếp theo
Để sắp xếp các quy trình theo thời điểm yêu cầu tiếp theo:
```
t
```

### Xóa tiến trình

#### Xóa theo mẫu
Để xóa tất cả các trò chơi khớp với một mẫu cụ thể:
```
delete [pattern]
```
**Ví dụ:**
```
delete HOT
```
Lệnh này sẽ xóa tất cả các tiến trình khớp với mẫu "HOT".

#### Xóa theo ID đơn
Để xóa một tiến trình theo ID của nó:
```
delete [ID]
```
**Ví dụ:**
```
delete 51
```
Lệnh này sẽ xóa tiến trình có ID 51.

#### Xóa theo dãy ID
Để xóa một loạt các quy trình theo ID của chúng:
```
delete [startID]-[endID]
```
**Ví dụ:**
```
delete 1-4
```
Lệnh này sẽ xóa tất cả các tiến trình từ ID 1 đến ID 4.

#### Xóa theo nhiều ID
Để xóa nhiều quy trình bằng ID của chúng, được phân tách bằng dấu phẩy:
```
delete [ID1],[ID2],[ID3]
```
**Ví dụ:**
```
delete 1,3,5
```
Lệnh này sẽ xóa các tiến trình có ID 1, 3 và 5.

### Xem nhật ký trạng thái

#### Xem 20 nhật ký trạng thái và số dư cuối cùng
Để xem 20 nhật ký trạng thái và số dư cuối cùng của một quy trình cụ thể:
```
status [ID]
```
**Ví dụ:**
```
status 5
```
This command will show the last 20 balance and status logs for the process with ID 5.

### Xem nhật ký PM2

#### Xem N dòng nhật ký PM2 cuối cùng
Để xem N dòng cuối cùng của nhật ký PM2 thô cho một quy trình cụ thể:
```
logs [ID] [lines]
```
**Ví dụ:**
```
logs 5 100
```
Lệnh này sẽ hiển thị 100 dòng nhật ký PM2 thô cuối cùng cho quy trình có ID 5.

### Thoát khỏi chương trình
Để thoát khỏi tập lệnh:
```
exit
```
hoặc chỉ cần nhấn enter mà không gõ bất kỳ lệnh nào.

## Ví dụ

1. **Xóa tất cả các trò chơi phù hợp với mẫu "Vertus":**
    ```
    delete Vertus
    ```

2. **Xóa tất cả tài khoản Telegram đã lưu:**
    ```
    delete Telegram
    ```

3. **Xóa các tiến trình trong phạm vi từ 1 đến 4:**
    ```
    delete 1-4
    ```

4. **Xóa tiến trình có ID 51:**
    ```
    delete 51
    ```

5. **Xóa các tiến trình có ID 1, 3 và 5:**
    ```
    delete 1,3,5
    ```

6. **Hiển thị 20 nhật ký trạng thái và số dư cuối cùng cho quy trình có ID 5:**
    ```
    status 5
    ```

7. **Hiển thị 100 dòng thô cuối cùng từ nhật ký PM2 cho quy trình có ID 5:**
    ```
    logs 5 100
    ```
