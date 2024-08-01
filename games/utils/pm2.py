#Bắt đầu quy trình PM2 mới
import subprocess
import sys

def start_pm2_app(script_path, app_name, session_name):
    interpreter_path = "venv/bin/python3"
    command = (
        f"NODE_NO_WARNINGS=1 pm2 start {script_path} "
        f"--name {app_name} "
        f"--interpreter {interpreter_path} "
        f"--watch {script_path} "
        f"--output /dev/null "  #Chuyển hướng thiết bị xuất chuẩn sang/dev/null
        f"--error {app_name}_error.log "  #Đăng nhập stderr vào một tệp cụ thể
        f"-- {session_name}"
    )
    subprocess.run(command, shell=True, check=True)

def save_pm2():
    command = "NODE_NO_WARNINGS=1 pm2 save"
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    print(result.stdout)
