#!/bin/bash

# Xác định thư mục đích và nguồn
TARGET_DIR="/app"
GAMES_DIR="$TARGET_DIR/games"
DEST_DIR="/usr/src/app/games"

# Kiểm tra xem thư mục có tồn tại không và có phải là kho lưu trữ git không
if [ -d "$TARGET_DIR" ] && [ -d "$TARGET_DIR/.git" ]; then
    echo "$TARGET_DIR kéo những thay đổi mới nhất."
    cd $TARGET_DIR
    git pull
elif [ -d "$TARGET_DIR" ]; then
    echo "$TARGET_DIR tồn tại nhưng không phải là kho lưu trữ git. Loại bỏ và nhân bản lại."
    rm -rf $TARGET_DIR
    git clone https://github.com/bibo318/telegram-claim-bot.git $TARGET_DIR
else
    echo "$TARGET_DIR does not exist. Cloning repository."
    git clone https://github.com/bibo318/telegram-claim-bot.git $TARGET_DIR
fi

# Đặt thư mục làm việc vào kho lưu trữ nhân bản
cd $GAMES_DIR

# Tạo thư mục đích
mkdir -p $DEST_DIR

# Sao chép đệ quy nội dung của thư mục trò chơi
cp -r $GAMES_DIR/* $DEST_DIR

echo "Tất cả các tập tin và thư mục con đã được sao chép vào $DEST_DIR"
