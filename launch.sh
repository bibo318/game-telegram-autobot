#!/bin/bash

# Chức năng kích hoạt môi trường ảo
activate_venv() {
    echo "Kích hoạt môi trường ảo..."
    source venv/bin/activate
}

# Chức năng hủy kích hoạt môi trường ảo
deactivate_venv() {
    echo "Hủy kích hoạt môi trường ảo..."
    deactivate
}

# Hàm chạy tập lệnh Python với các đối số bổ sung
run_script() {
    local script=$1
    shift  # Chuyển qua tên tập lệnh để nhận bất kỳ tham số bổ sung nào
    echo "Tập lệnh đang chạy: $script có đối số: $@"
    python3 "$script" "$@"
}

# Chức năng liệt kê và chọn script
list_and_choose_script() {
    echo "Liệt kê các tập lệnh có sẵn trong thư mục hiện tại và thư mục ./games:"
    # Liệt kê tất cả các tập lệnh Python trong thư mục hiện tại và thư mục ./games
    IFS=$'\n' read -d '' -r -a scripts < <(find . ./games -maxdepth 1 -name "*.py" -print && printf '\0')
    
    if [ ${#scripts[@]} -eq 0 ]; then
        echo "Không tìm thấy tập lệnh Python nào trong thư mục hiện tại hoặc thư mục ./games."
        exit 1
    fi

    # Liệt kê tất cả các tập lệnh được tìm thấy
    for i in "${!scripts[@]}"; do
        echo "$((i+1))) ${scripts[$i]}"
    done

    # Nhắc người dùng chọn tập lệnh
    echo "Vui lòng chọn tập lệnh theo số:"
    read -r choice
    selected_script="${scripts[$((choice-1))]}"
    
    if [ -n "$selected_script" ]; then
        activate_venv
        run_script "$selected_script" "${@:2}"
        deactivate_venv
    else
        echo "Lựa chọn không hợp lệ. Đang thoát..."
        exit 1
    fi
}

# Kiểm tra xem đối số tập lệnh có được cung cấp không
if [ -z "$1" ]; then
    list_and_choose_script
else
    # Nối '.py' nếu nó không có trong tên tập lệnh
    script_name="$1"
    if [[ ! "$script_name" == *".py" ]]; then
        script_name="${script_name}.py"
    fi

    # Kiểm tra xem tập lệnh có tồn tại trong thư mục ./games hoặc thư mục hiện tại không
    if [ -f "./games/$script_name" ]; then
        script_path="./games/$script_name"
    elif [ -f "$script_name" ]; then
        script_path="$script_name"
    else:
        echo "Không tìm thấy tập lệnh được chỉ định trong thư mục ./games hoặc thư mục hiện tại."
        list_and_choose_script
        exit 1
    fi

    activate_venv
    run_script "$script_path" "${@:2}"
    deactivate_venv
fi