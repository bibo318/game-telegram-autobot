import json
import subprocess
from datetime import datetime
import re
import os

def run_command(command):
    return subprocess.run(command, text=True, shell=True, capture_output=True).stdout

def parse_time_from_log(line):
    try:
        time_str = line.split("Cần đợi cho đến khi ")[1].split(' before')[0]
        try:
            parsed_time = datetime.strptime(time_str, "%d %B - %H:%M")
        except ValueError:
            parsed_time = datetime.strptime(time_str, "%H:%M")
        return parsed_time
    except Exception as e:
        print(f"Không thể phân tích thời gian từ dòng: {line}. Lỗi: {e}")
        return None

def truncate_and_pad(string, length):
    string = string or "None"
    return (string[:length-3] + '...').ljust(length) if len(string) > length else string.ljust(length)

def extract_detail(line, keyword):
    return line.split(f"{keyword}:")[1].strip() if keyword in line else "None"

def fetch_and_process_logs(process_name):
    sanitized_process_name = process_name.replace(':', '-').replace('_', '-')
    log_file = f"/root/.pm2/logs/{sanitized_process_name}-out.log"
    logs = run_command(f"tail -n 200 {log_file}")

    balance = "None"
    profit_hour = "None"
    next_claim_at = "None"
    log_status = "None"

    relevant_lines = [line for line in reversed(logs.splitlines()) if any(kw in line for kw in ["BALANCE:", "STATUS:", "Need to wait until", "PROFIT/HOUR:"])]

    for line in relevant_lines:
        if "BALANCE:" in line and balance == "None":
            balance = extract_detail(line, "BALANCE")
        if "PROFIT/HOUR:" in line and profit_hour == "None":
            profit_hour = extract_detail(line, "PROFIT/HOUR")
        if "STATUS:" in line and log_status == "None":
            log_status = extract_detail(line, "STATUS")
        if "Need to wait until" in line and next_claim_at == "None":
            next_claim_at = parse_time_from_log(line)
            if next_claim_at is not None:
                next_claim_at = next_claim_at.strftime("%d %B - %H:%M")

    return process_name, balance, profit_hour, next_claim_at, log_status

def display_processes(processes, status, sort_by="time", start_index=1):
    name_width = 20
    balance_width = 20
    profit_hour_width = 20
    claim_width = 20
    status_width = 80
    total_width = name_width + balance_width + profit_hour_width + claim_width + status_width + 18

    print(f"{status} Wallet Processes:\n")
    print("|-" + "-" * total_width + "-|")
    print(f"| {'ID'.ljust(3)} | {'Wallet Name'.ljust(name_width)} | {'Balance'.ljust(balance_width)} | {'Profit/Hour'.ljust(profit_hour_width)} | {'Next Claim'.ljust(claim_width)} | {'Status'.ljust(status_width)} |")
    print("|-" + "-" * total_width + "-|")

    process_list = []
    for process_name in processes:
        if process_name.strip():
            name, balance, profit_hour, next_claim_at, log_status = fetch_and_process_logs(process_name.strip())
            process_list.append((name, balance, profit_hour, next_claim_at, log_status))

    if sort_by == "time":
        process_list.sort(key=lambda x: datetime.strptime(x[2], "%d %B - %H:%M") if x[2] != "None" else datetime.max)
    elif sort_by == "name":
        process_list.sort(key=lambda x: x[0])

    for i, (name, balance, profit_hour, next_claim_at, log_status) in enumerate(process_list, start=start_index):
        name = truncate_and_pad(name, name_width)
        balance = truncate_and_pad(balance, balance_width)
        profit_hour = truncate_and_pad(profit_hour, claim_width)
        next_claim_at = truncate_and_pad(next_claim_at, claim_width)
        log_status = truncate_and_pad(log_status, status_width)
        print(f"| {str(i).ljust(3)} | {name} | {balance} | {profit_hour} | {next_claim_at} | {log_status} |")

    print("|-" + "-" * total_width + "-|")
    return process_list

def remove_directories(dir_name):
    print(f"Removing directories for {dir_name}...")
    run_command(f"rm -rf ./selenium/{dir_name}")
    run_command(f"rm -rf ./backups/{dir_name}")
    run_command(f"rm -rf ./screenshots/{dir_name}")
    print(f"Đã xóa thư mục cho {dir_name}")

def list_all_pm2_processes():
    return run_command("pm2 list --no-color | awk '{{print $4}}'").splitlines()

def list_pm2_processes(status_filter):
    return run_command(f"pm2 list --no-color | grep {status_filter} | awk '{{print $4}}'").splitlines()

def get_inactive_directories():
    output = run_command("pm2 jlist")

    process_list = json.loads(output)
    active_process_names = [proc['name'] for proc in process_list if proc['pm2_env']['status'] == 'online']
    
    all_sessions = [d for d in os.listdir('./selenium') if os.path.isdir(os.path.join('./selenium', d))]

    inactive_sessions = set(all_sessions) - set(active_process_names)

    return list(inactive_sessions)

def delete_process_by_id(process_id, process_list):
    if process_id <= len(process_list):
        process_name = process_list[process_id - 1][0].strip()
        run_command(f"pm2 stop {process_name}")
        run_command(f"pm2 delete {process_name}")
        run_command(f"pm2 save")
        remove_directories(process_name)
        print(f"Đã dừng và xóa quá trình {process_name} khỏi PM2.")
        process_list.pop(process_id - 1)
    else:
        print("ID tiến trình không hợp lệ.")

def delete_processes_by_ids(ids, process_list):
    for process_id in sorted(ids, reverse=True):
        delete_process_by_id(process_id, process_list)

def delete_process_by_pattern(pattern, process_list):
    for process in process_list[:]:
        if re.search(pattern, process[0]):
            run_command(f"pm2 stop {process[0]}")
            run_command(f"pm2 delete {process[0]}")
            run_command(f"pm2 save")
            remove_directories(process[0])
            print(f"Đã dừng và xóa quá trình {process[0]} khỏi PM2.")
            process_list.remove(process)

def show_logs(process_id, process_list, lines=30):
    print(get_logs(process_id, process_list, lines))
    input("Nhấn Enter để tiếp tục...")

def get_logs(process_id, process_list, lines=30):
    if process_id > len(process_list):
        return "ID tiến trình không hợp lệ."
    
    return get_logs_by_process_name(process_list[process_id - 1][0], lines)

def get_logs_by_process_name(process_name, lines=30):
    process_name = process_name.strip().replace('_', '-')
    sanitized_process_name = process_name.replace(':', '-')
    log_file = f"/root/.pm2/logs/{sanitized_process_name}-out.log"
    logs = run_command(f"tail -n {lines} {log_file}")
    return logs

def show_status_logs(process_id, process_list):
    print(get_status_logs(process_id, process_list))
    input("Nhấn Enter để tiếp tục...")

def get_status_logs(process_id, process_list):
    if process_id > len(process_list):
        return "ID tiến trình không hợp lệ."
    
    return get_logs_by_process_name(process_list[process_id - 1][0])

def get_status_logs_by_process_name(process_name):
    process_name = process_name.strip().replace('_', '-')
    sanitized_process_name = process_name.replace(':', '-')
    log_file = f"/root/.pm2/logs/{sanitized_process_name}-out.log"
    logs = run_command(f"grep -E 'BALANCE:|STATUS:' {log_file} | tail -n 20")
    return logs

def parse_delete_ids(delete_ids_str):
    ids = set()
    parts = delete_ids_str.split(',')
    for part in parts:
        if '-' in part:
            start, end = part.split('-')
            ids.update(range(int(start), int(end) + 1))
        else:
            ids.add(int(part))
    return sorted(ids)

def main():
    print("Đọc dữ liệu từ PM2 -việc này có thể mất chút thời gian nếu bạn có nhiều Game.")
    while True:
        stopped_processes = list_pm2_processes("stopped")
        running_processes = list_pm2_processes("online")
        inactive_directories = get_inactive_directories()

        print(f"Đã tìm thấy {len(inactive_directories)} thư mục không hoạt động trong Selenium.")

        print("\nQuy trình không hoạt động:")
        stopped_process_list = display_processes(stopped_processes + inactive_directories, "Stopped", sort_by="name", start_index=1)
        print("\nQuy trình hoạt động:")
        running_process_list = display_processes(running_processes, "Running", sort_by="name", start_index=len(stopped_process_list) + 1)

        print("\nOptions:")
        print("'t' - Sắp xếp theo thời gian yêu cầu tiếp theo")
        print("'delete [ID]' - Xóa quy trình theo số (ví dụ: một ID -'1', phạm vi '1-3' hoặc nhiều '1,3')")
        print("'delete [pattern]' - Xóa tất cả các quy trình khớp với mẫu (ví dụ: HOT, Blum, Wave)")
        print("'status [ID]' - Hiển thị 20 số dư cuối cùng và trạng thái của quy trình đã chọn")
        print("'logs [ID] [lines]' - Hiển thị 'n' dòng cuối cùng của nhật ký PM2 cho quy trình (mặc định: 30)")
        print("'exit' or hit enter - Thoát khỏi chương trình")

        user_input = input("\nNhập lựa chọn của bạn: ").strip()

        if user_input == 't':
            display_processes(stopped_processes + inactive_directories, "Stopped", sort_by="time", start_index=1)
            display_processes(running_processes, "Running", sort_by="time", start_index=len(stopped_process_list) + 1)
            input("Nhấn Enter để tiếp tục...")
        elif user_input.startswith("delete "):
            try:
                delete_ids_str = user_input.split()[1]
                delete_ids = parse_delete_ids(delete_ids_str)
                delete_processes_by_ids(delete_ids, stopped_process_list + running_process_list)
            except ValueError:
                delete_pattern = user_input.split()[1]
                delete_process_by_pattern(f".*{delete_pattern}.*", stopped_process_list + running_process_list)
        elif user_input.startswith("status "):
            try:
                status_id = int(user_input.split()[1])
                if status_id <= len(stopped_process_list):
                    show_status_logs(status_id, stopped_process_list)
                else:
                    show_status_logs(status_id - len(stopped_process_list), running_process_list)
            except ValueError:
                print("ID không hợp lệ.")
        elif user_input.startswith("logs "):
            try:
                logs_id = int(user_input.split()[1])
                lines = int(user_input.split()[2]) if len(user_input.split()) > 2 else 30
                if logs_id <= len(stopped_process_list):
                    show_logs(logs_id, stopped_process_list, lines)
                else:
                    show_logs(logs_id - len(stopped_process_list), running_process_list, lines)
            except ValueError:
                print("Đâu vao không hợp lệ.")
        elif user_input == "exit" or user_input == "":
            break
        else:
            print("Tùy chọn không hợp lệ. Vui lòng thử lại.")

if __name__ == "__main__":
    main()