#!/bin/bash

while true; do
    # Chạy tập lệnh pull-games.sh
    ./pull-games.sh

    # Hiển thị ngày và giờ hiện tại
    echo "Tập lệnh được thực thi tại: $(date)"

    # Nhàn rỗi trong 24 giờ
    sleep 43200  # 43200 seconds = 12 hours
done