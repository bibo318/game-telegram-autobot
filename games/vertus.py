import os
import shutil
import sys
import time
import re
import json
import getpass
import random
import subprocess
from PIL import Image
from pyzbar.pyzbar import decode
import qrcode_terminal
import fcntl
from fcntl import flock, LOCK_EX, LOCK_UN, LOCK_NB
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException, ElementClickInterceptedException, UnexpectedAlertPresentException
from datetime import datetime, timedelta

def load_settings():
    global settings, settings_file
    default_settings = {
        "forceClaim": False,
        "debugIsOn": False,
        "hideSensitiveInput": True,
        "screenshotQRCode": True,
        "maxSessions": 1,
        "verboseLevel": 2,
        "lowestClaimOffset": 0,
        "highestClaimOffset": 15,
        "forceNewSession": False,
        "useProxy": False,
        "proxyAddress": "http://127.0.0.1:8080"
    }

    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            loaded_settings = json.load(f)
        #Lọc các cài đặt không sử dụng từ các phiên bản trước
        settings = {k: loaded_settings.get(k, v) for k, v in default_settings.items()}
        output("Đã tải cài đặt thành công.", 3)
    else:
        settings = default_settings
        save_settings()

def save_settings():
    global settings, settings_file
    with open(settings_file, "w") as f:
        json.dump(settings, f)
    output("Cài đặt đã lưu thành công.", 3)

def output(string, level):
    if settings['verboseLevel'] >= level:
        print(string)

#Xác định phiên và tập tin cài đặt
settings_file = "variables.txt"
status_file_path = "status.txt"
settings = {}
load_settings()
driver = None
target_element = None
random_offset = random.randint(settings['lowestClaimOffset'], settings['highestClaimOffset'])
script = "games/vertus.py"
prefix = "Vertus:"
url = "https://web.telegram.org/k/#@vertus_app_bot"

def increase_step():
    global step
    step_int = int(step) + 1
    step = f"{step_int:02}"

print(f"Khởi tạo tập lệnh Python tự động xác nhận ví {prefix} - Chúc may mắn!")

def update_settings():
    global settings

    def update_setting(setting_key, message, default_value):
        current_value = settings.get(setting_key, default_value)
        response = input(f"\n{message} (Y/N, nhấn Enter để cập nhật [{current_value}]): ").strip().lower()
        if response == "y":
            settings[setting_key] = True
        elif response == "n":
            settings[setting_key] = False

    update_setting("forceClaim", "Chúng ta có nên force claim trong lần chạy đầu tiên không? Không đợi đồng hồ đầy", settings["forceClaim"])
    update_setting("debugIsOn", "Chúng ta có nên kích hoạt tính năng debugs không? Điều này sẽ lưu ảnh chụp màn hình vào ổ đĩa cục bộ của bạn", settings["debugIsOn"])
    update_setting("hideSensitiveInput", "Chúng ta có nên ẩn đầu vào nhạy cảm? Số điện thoại và cụm từ active key của bạn sẽ không hiển thị trên màn hình", settings["hideSensitiveInput"])
    update_setting("screenshotQRCode", "Chúng tôi có cho phép đăng nhập bằng mã QR không? Cách thay thế là bằng số điện thoại và mật khẩu một lần", settings["screenshotQRCode"])

    try:
        new_max_sessions = int(input(f"\nNhập số phiên yêu cầu đồng thời tối đa. Các yêu cầu bổ sung sẽ xếp hàng cho đến khi còn chỗ trống.\n(current: {settings['maxSessions']}): "))
        settings["maxSessions"] = new_max_sessions
    except ValueError:
        output("Number of sessions remains unchanged.", 1)

    try:
        new_verbose_level = int(input("\nNhập số lượng thông tin bạn muốn hiển thị trong bảng điều khiển.\n 3 = tất cả tin nhắn, 2 = các bước xác nhận, 1 = các bước tối thiểu\n(current: {}): ".format(settings['verboseLevel'])))
        if 1 <= new_verbose_level <= 3:
            settings["verboseLevel"] = new_verbose_level
            output("Đã cập nhật cấp độ chi tiết thành công.", 2)
        else:
            output("Mức độ dài dòng không thay đổi.", 2)
    except ValueError:
        output("Mức độ dài dòng không thay đổi.", 2)

    try:
        new_lowest_offset = int(input("\nNhập mức chênh lệch thấp nhất có thể có cho bộ đếm thời gian xác nhận quyền sở hữu (giá trị hợp lệ là -30 đến +30 phút)\n(hiện tại: {}): ".format(settings['lowestClaimOffset'])))
        if -30 <= new_lowest_offset <= 30:
            settings["lowestClaimOffset"] = new_lowest_offset
            output("Đã cập nhật thành công khoản bù đắp yêu cầu claim thấp nhất.", 2)
        else:
            output("Phạm vi không hợp lệ cho mức bù đắp yêu cầu claim thấp nhất. Vui lòng nhập giá trị từ -30 đến +30.", 2)
    except ValueError:
        output("Mức claim thấp nhất không thay đổi.", 2)

    try:
        new_highest_offset = int(input("\nEnter the highest possible offset for the claim timer (valid values are 0 to 60 minutes)\n(current: {}): ".format(settings['highestClaimOffset'])))
        if 0 <= new_highest_offset <= 60:
            settings["highestClaimOffset"] = new_highest_offset
            output("Higphần bù yêu cầu hest được cập nhật thành công.", 2)
        else:
            output("Invalid range for highest claim offset. Please enter a value between 0 and 60.", 2)
    except ValueError:
        output("Highest claim offset remains unchanged.", 2)

    if settings["lowestClaimOffset"] > settings["highestClaimOffset"]:
        settings["lowestClaimOffset"] = settings["highestClaimOffset"]
        output("Adjusted lowest claim offset to match the highest as it was greater.", 2)

    update_setting("useProxy", "Use Proxy?", settings["useProxy"])

    if settings["useProxy"]:
        proxy_address = input(f"\nEnter the Proxy IP address and port (current: {settings['proxyAddress']}): ").strip()
        if proxy_address:
            settings["proxyAddress"] = proxy_address

    save_settings()

    update_setting("forceNewSession", "Overwrite existing session and Force New Login? Use this if your saved session has crashed\nOne-Time only (setting not saved): ", settings["forceNewSession"])

    output("\nRevised settings:", 1)
    for key, value in settings.items():
        output(f"{key}: {value}", 1)
    output("", 1)

def get_session_id():
    """Nhắc người dùng nhập ID phiên hoặc xác định ID  tiếp theo dựa trên prefix 'Ví'.

    Returns:
        str: ID phiên đã nhập hoặc ID  được tạo tự động.
    """
    global settings, prefix
    output(f"Phiên của bạn sẽ có prefix là: {prefix}", 1)
    user_input = input("Nhập Tên phiên duy nhất của bạn tại đây hoặc nhấn <enter> cho ví  tiếp theo: ").strip()

    #Đặt thư mục lưu trữ các thư mục phiên
    screenshots_dir = "./screenshots/"

    #Đảm bảo thư mục tồn tại để tránh FileNotFoundError
    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir)

    #Liệt kê nội dung của thư mục
    try:
        dir_contents = os.listdir(screenshots_dir)
    except Exception as e:
        output(f"Lỗi truy cập vào thư mục: {e}", 1)
        return None  #hoặc xử lý lỗi theo cách khác
#Lọc các thư mục có tiền tố 'Wallet' và trích xuất các phần số
    wallet_dirs = [int(dir_name.replace(prefix + 'Wallet', ''))
                   for dir_name in dir_contents
                   if dir_name.startswith(prefix + 'Wallet') and dir_name[len(prefix) + 6:].isdigit()]

    #Tính ID ví tiếp theo
    next_wallet_id = max(wallet_dirs) + 1 if wallet_dirs else 1

    #Sử dụng ID ví tuần tự tiếp theo nếu không có thông tin đầu vào nào của người dùng được cung cấp
    if not user_input:
        user_input = f"Wallet{next_wallet_id}"  #Đảm bảo ID đầy đủ được đặt tiền tố chính xác

    return prefix+user_input


#Cập nhật cài đặt dựa trên đầu vào của người dùng
if len(sys.argv) > 1:
        user_input = sys.argv[1]  #Nhận ID phiên từ đối số dòng lệnh
        output(f"ID phiên được cung cấp: {user_input}",2)
        #Kiểm tra an toàn đối số thứ hai
        if len(sys.argv) > 2 and sys.argv[2] == "debug":
            settings['debugIsOn'] = True
else:
    output("\nCài đặt hiện tại:",1)
    for key, value in settings.items():
        output(f"{key}: {value}",1)
    user_input = input("\Chúng tôi có nên cập nhật cài đặt của bạn không? (Mặc định:<enter> / Yes = y): ").strip().lower()
    if user_input == "y":
        update_settings()
    user_input = get_session_id()

session_path = "./selenium/{}".format(user_input)
os.makedirs(session_path, exist_ok=True)
screenshots_path = "./screenshots/{}".format(user_input)
os.makedirs(screenshots_path, exist_ok=True)
backup_path = "./backups/{}".format(user_input)
os.makedirs(backup_path, exist_ok=True)
step = "01"

#Xác định đường dẫn cơ sở của chúng tôi để gỡ lỗi ảnh chụp màn hình
screenshot_base = os.path.join(screenshots_path, "screenshot")

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={session_path}")
    chrome_options.add_argument("--headless")  #Đảm bảo tính năng không đầu được bật
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/124.0.2478.50 Version/17.0 Mobile/15E148 Safari/604.1"
    chrome_options.add_argument(f"user-agent={user_agent}")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    if settings["useProxy"]:
        proxy_server = settings["proxyAddress"]
        chrome_options.add_argument(f"--proxy-server={proxy_server}")

    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--test-type")

    chromedriver_path = shutil.which("chromedriver")
    if chromedriver_path is None:
        output("Không tìm thấy ChromeDriver trong PATH. Hãy đảm bảo nó đã được cài đặt.", 1)
        exit(1)

    try:
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        output(f"Quá trình thiết lập ChromeDriver ban đầu có thể đã thất bại: {e}", 1)
        output("Hãy đảm bảo bạn có phiên bản ChromeDriver chính xác cho hệ thống của mình.", 1)
        exit(1)

def run_http_proxy():
    proxy_lock_file = "./start_proxy.txt"
    max_wait_time = 15 * 60  #15 phút
    wait_interval = 5  #5 giây
    start_time = time.time()

    while os.path.exists(proxy_lock_file) and (time.time() - start_time) < max_wait_time:
        output("Proxy is already running. Waiting for it to free up...", 1)
        time.sleep(wait_interval)

    if os.path.exists(proxy_lock_file):
        output("Max wait time elapsed. Proceeding to run the proxy.", 1)

    with open(proxy_lock_file, "w") as lock_file:
        lock_file.write(f"Proxy started at: {time.ctime()}\n")

    try:
        subprocess.run(['./launch.sh', 'enable-proxy'], check=True)
        output("http-proxy started successfully.", 1)
    except subprocess.CalledProcessError as e:
        output(f"Failed to start http-proxy: {e}", 1)
    finally:
        os.remove(proxy_lock_file)

settings["useProxy"] = True
settings["proxyAddress"] = "http://127.0.0.1:8080"

if settings["useProxy"] and settings["proxyAddress"] == "http://127.0.0.1:8080":
    run_http_proxy()
else:
    output("Proxy bị vô hiệu hóa trong cài đặt.",2)

def get_driver():
    global driver
    if driver is None:  #Kiểm tra xem trình điều khiển có cần được khởi tạo không
        manage_session()  #Đảm bảo chúng ta có thể bắt đầu một phiên
        driver = setup_driver()
        output("\BAN ĐẦU TRÌNH ĐIỀU KHIỂN CHROME: Cố gắng không thoát khỏi tập lệnh trước khi nó tách ra.",2)
    return driver

def quit_driver():
    global driver
    if driver:
        driver.quit()
        output("\BỎ LỖI ĐIỀU KHIỂN CHROME: Hiện phiên đã thoát khỏi tập lệnh.",2)
        driver = None
        release_session()  #Đánh dấu phiên là đã đóng

def manage_session():
    current_session = session_path
    current_timestamp = int(time.time())
    session_started = False
    new_message = True
    output_priority = 1

    while True:
        try:
            with open(status_file_path, "r+") as file:
                flock(file, LOCK_EX)
                status = json.load(file)

                #Dọn dẹp các phiên hết hạn
                for session_id, timestamp in list(status.items()):
                    if current_timestamp - timestamp > 300:  #5 phút
                        del status[session_id]
                        output(f"Đã xóa phiên hết hạn: {session_id}", 3)

                #Kiểm tra các vị trí có sẵn, loại trừ phiên hiện tại khỏi số lượng
                active_sessions = {k: v for k, v in status.items() if k != current_session}
                if len(active_sessions) < settings['maxSessions']:
                    status[current_session] = current_timestamp
                    file.seek(0)
                    json.dump(status, file)
                    file.truncate()
                    output(f"Phiên đã bắt đầu: {current_session} in {status_file_path}", 3)
                    flock(file, LOCK_UN)
                    session_started = True
                    break
                flock(file, LOCK_UN)

            if not session_started:
                output(f"Đang chờ slot. Phiên hiện tại: {len(active_sessions)}/{settings['maxSessions']}", output_priority)
                if new_message:
                    new_message = False
                    output_priority = 3
                time.sleep(random.randint(5, 15))
            else:
                break

        except FileNotFoundError:
            #Tạo tập tin nếu nó không tồn tại
            with open(status_file_path, "w") as file:
                flock(file, LOCK_EX)
                json.dump({}, file)
                flock(file, LOCK_UN)
        except json.decoder.JSONDecodeError:
            #Xử lý JSON trống hoặc bị hỏng
            with open(status_file_path, "w") as file:
                flock(file, LOCK_EX)
                output("Tệp trạng thái bị hỏng. Đặt lại...", 3)
                json.dump({}, file)
                flock(file, LOCK_UN)

def release_session():
    current_session = session_path
    current_timestamp = int(time.time())

    with open(status_file_path, "r+") as file:
        flock(file, LOCK_EX)
        status = json.load(file)
        if current_session in status:
            del status[current_session]
            file.seek(0)
            json.dump(status, file)
            file.truncate()
        flock(file, LOCK_UN)
        output(f"Phiên phát hành: {current_session}", 3)
 
def log_into_telegram():
    global driver, target_element, session_path, screenshots_path, backup_path, settings, step
    step = "01"

    def visible_QR_code():
        global driver, screenshots_path, step
        max_attempts = 5
        attempt_count = 0
        last_url = "not a url"  #Trình giữ chỗ cho URL mã QR được phát hiện gần đây nhất

        xpath = "//canvas[@class='qr-canvas']"
        driver.get(url)
        wait = WebDriverWait(driver, 30)
        output(f"Step {step} - Chờ mã QR đầu tiên -có thể mất tới 30 giây.", 1)
        increase_step()
        QR_code = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))

        if not QR_code:
            return False

        wait = WebDriverWait(driver, 2)

        while attempt_count < max_attempts:
            try:
                QR_code = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
                QR_code.screenshot(f"{screenshots_path}/Step {step} - Initial QR code.png")
                image = Image.open(f"{screenshots_path}/Step {step} - Initial QR code.png")
                decoded_objects = decode(image)
                if decoded_objects:
                    this_url = decoded_objects[0].data.decode('utf-8')
                    if this_url != last_url:
                        last_url = this_url  #Cập nhật URL nhìn thấy lần cuối
                        attempt_count += 1
                        output("*** Quan trọng: Việc mở @game-telegram-autobot trong Ứng dụng Telegram của bạn có thể ngăn tập lệnh này đăng nhập! ***\N", 2)
                        output(f"Bước {step} - Đường dẫn ảnh chụp màn hình của chúng tôi là {screenshots_path}\n", 1)
                        output(f"Bước {step} - Tạo ảnh chụp màn hình {attempt_count} của {max_attempts}\n", 2)
                        qrcode_terminal.draw(this_url)
                    if attempt_count >= max_attempts:
                        output(f"Bước {step} - Đã đạt số lần thử tối đa mà không có mã QR mới.", 1)
                        return False
                    time.sleep(0.5)  #Chờ trước lần kiểm tra tiếp theo
                else:
                    time.sleep(0.5)  #Không có mã QR nào được giải mã, hãy đợi trước khi thử lại
            except TimeoutException:
                output(f"Bước {step} - Mã QR không còn hiển thị nữa.", 2)
                return True  #Cho biết mã QR đã được quét hoặc biến mất
        
        output(f"Bước {step} - Không tạo được mã QR hợp lệ sau nhiều lần thử.", 1)
        return False  #Nếu vòng lặp hoàn tất mà không quét thành công

    driver = get_driver()
    
    #Phương pháp mã QR
    if settings['screenshotQRCode']:
        try:

            while True:
                if visible_QR_code():  #Không tìm thấy mã QR
                    test_for_2fa()
                    return  #Thoát hoàn toàn chức năng
#Nếu chúng ta đến đây nghĩa là mã QR vẫn còn:
                choice = input(f"\nStep {step} - Mã QR vẫn còn. Thử lại (r) bằng mã QR mới hoặc chuyển sang phương thức OTP (nhập): ")
                print("")
                if choice.lower() == 'r':
                    visible_QR_code()
                else:
                    break

        except TimeoutException:
            output(f"Bước {step} - Không tìm thấy canvas: Khởi động lại tập lệnh và thử lại Mã QR hoặc chuyển sang phương thức OTP.", 1)

    #Phương thức đăng nhập OTP
    increase_step()
    output(f"Bước {step} - Khởi tạo phương thức Mật khẩu một lần (OTP)...\n",1)
    driver.get(url)
    xpath = "//button[contains(@class, 'btn-primary') and contains(., 'Đăng nhập bằng số điện thoại')]"
    target_element=move_and_click(xpath, 30, False, "chuyển sang đăng nhập bằng số điện thoại", step, "visible")
    target_element.click()
    increase_step()

    #Lựa chọn mã quốc gia
    xpath = "//div[@class='input-field-input']"    
    target_element = move_and_click(xpath, 30, False, "cập nhật quốc gia của người dùng", step, "visible")
    target_element.click()
    user_input = input(f"Bước {step} -Vui lòng nhập Tên quốc gia của bạn giống như xuất hiện trong danh sách Telegram: ").strip()  
    target_element.send_keys(user_input)
    target_element.send_keys(Keys.RETURN)
    increase_step()

    #Nhập số điện thoại
    xpath = "//div[@class='input-field-input' and @inputmode='decimal']"
    target_element = move_and_click(xpath, 30, False, "yêu cầu số điện thoại của người dùng", step, "visible")
    driver.execute_script("arguments[0].click();", target_element)
    def validate_phone_number(phone):
        #Regex để xác thực số điện thoại quốc tế không có số 0 đứng đầu và thường dài từ 7 đến 15 chữ số
        pattern = re.compile(r"^[1-9][0-9]{6,14}$")
        return pattern.match(phone)

    while True:
        if settings['hideSensitiveInput']:
            user_phone = getpass.getpass(f"Bước {step} -Vui lòng nhập số điện thoại của bạn không dẫn đầu số 0 (đầu vào ẩn): ")
        else:
            user_phone = input(f"Bước {step} -Vui lòng nhập số điện thoại của bạn không dẫn đầu số 0 (đầu vào hiển thị): ")
    
        if validate_phone_number(user_phone):
            output(f"Bước {step} -Đã nhập số điện thoại hợp lệ.",3)
            break
        else:
            output(f"Bước {step} -Số điện thoại không hợp lệ, phải dài từ 7 đến 15 chữ số và không có số 0 đứng đầu.",1)
    target_element.send_keys(user_phone)
    increase_step()

    #Đợi nút "Tiếp theo" có thể nhấp được và nhấp vào nút đó
    xpath = "//button//span[contains(text(), 'Next')]"
    target_element = move_and_click(xpath, 15, False, "nhấp vào tiếp theo để tiến hành nhập OTP", step, "visible")
    driver.execute_script("arguments[0].click();", target_element)
    increase_step()

    try:
        #Cố gắng xác định vị trí và tương tác với trường OTP
        wait = WebDriverWait(driver, 20)
        if settings['debugIsOn']:
            time.sleep(3)
            driver.save_screenshot(f"{screenshots_path}/Step {step} - Ready_for_OTP.png")
        password = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='tel']")))
        otp = input(f"Bước {step} -Telegram OTP từ ứng dụng của bạn là gì? ")
        password.click()
        password.send_keys(otp)
        output(f"Bước {step} -Hãy thử đăng nhập bằng Telegram OTP của bạn.\n",3)
        increase_step()

    except TimeoutException:
        #Kiểm tra bộ nhớ ngoại tuyến
        xpath = "//button[contains(text(), 'STORAGE_OFFLINE')]"
        target_element = move_and_click(xpath, 8, False, "check for 'STORAGE_OFFLINE'", step, "visible")
        if target_element:
            output(f"Step {step} - ***Progress is blocked by a 'STORAGE_OFFLINE' button",1)
            output(f"Step {step} - If you are re-using an old Wallet session; try to delete or create a new session.",1)
            found_error = True
        #Kiểm tra chờ lũ
        xpath = "//button[contains(text(), 'FLOOD_WAIT')]"
        target_element = move_and_click(xpath, 8, False, "check for 'FLOOD_WAIT'", step, "visible")
        if target_element:
            output(f"Bước {step} - ***Tiến trình bị chặn bởi nút 'FLOOD_WAIT'", 1)
            output(f"Bước {step} -Bạn cần đợi số giây được chỉ định trước khi thử lại.", 1)
            output(f"Bước {step} - {target_element.text}")
            found_error = True
        if not found_error:
            output(f"Bước {step} -Selenium không thể tương tác với màn hình OTP vì lý do không xác định.")

    except Exception as e:  #Bắt bất kỳ lỗi không mong muốn nào khác
        output(f"Bước {step} -Đăng nhập không thành công. Lỗi: {e}", 1) 
        if settings['debugIsOn']:
            driver.save_screenshot(f"{screenshots_path}/Step {step} - error_Something_Occured.png")

    increase_step()
    test_for_2fa()

    if settings['debugIsOn']:
        time.sleep(3)
        driver.save_screenshot(f"{screenshots_path}/Step {step} - After_Entering_OTP.png")

def test_for_2fa():
    global settings, driver, screenshots_path, step
    try:
        increase_step()
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        xpath = "//input[@type='password' and contains(@class, 'input-field-input')]"
        fa_input = move_and_click(xpath, 10, False, "kiểm tra yêu cầu 2FA (sẽ hết thời gian chờ nếu bạn không có 2FA)", step, "present")
        if fa_input:
            if settings['hideSensitiveInput']:
                tg_password = getpass.getpass(f"Bước {step} -Nhập mật khẩu Telegram 2FA của bạn: ")
            else:
                tg_password = input(f"Bước {step} -Nhập mật khẩu Telegram 2FA của bạn: ")
            fa_input.send_keys(tg_password + Keys.RETURN)
            output(f"Bước {step} -mật khẩu 2FA đã được gửi.\n", 3)
            output(f"Bước {step} -Kiểm tra xem mật khẩu 2FA có đúng không.\n", 2)
            xpath = "//*[contains(text(), 'mật khẩu không đúng')]"
            try:
                incorrect_password = WebDriverWait(driver, 3).until(EC.visibility_of_element_located((By.XPATH, xpath)))
                output(f"Bước {step} -Mật khẩu 2FA được Telegram đánh dấu là không chính xác -hãy kiểm tra ảnh chụp màn hình gỡ lỗi của bạn nếu đang hoạt động.", 1)
                if settings['debugIsOn']:
                    screenshot_path = f"{screenshots_path}/Bước {step} -Kiểm tra mã QR sau khi phiên tiếp tục.png"
                    driver.save_screenshot(screenshot_path)
                quit_driver()
                sys.exit()  #Thoát nếu phát hiện mật khẩu sai
            except TimeoutException:
                pass

            output(f"Bước {step} -Không tìm thấy lỗi mật khẩu.", 3)
            xpath = "//input[@type='password' and contains(@class, 'input-field-input')]"
            fa_input = move_and_click(xpath, 5, False, "kiểm tra lần cuối để đảm bảo chúng tôi đã đăng nhập chính xác", step, "present")
            if fa_input:
                output(f"Bước {step} -Mục nhập mật khẩu 2FA vẫn hiển thị, hãy kiểm tra ảnh chụp màn hình gỡ lỗi của bạn để biết thêm thông tin.\n", 1)
                sys.exit()
            output(f"Bước {step} -Kiểm tra mật khẩu 2FA dường như đã thành công.\n", 3)
        else:
            output(f"Bước {step} -Không tìm thấy trường nhập 2FA.\n", 1)

    except TimeoutException:
        #Không tìm thấy trường 2FA
        output(f"Bước {step} -Không cần ủy quyền hai yếu tố.\n", 3)

    except Exception as e:  #Bắt bất kỳ lỗi không mong muốn nào khác
        output(f"Bước {step} -Đăng nhập không thành công. Lỗi 2FA -có thể bạn sẽ cần phải khởi động lại tập lệnh: {e}", 1)
        if settings['debugIsOn']:
            screenshot_path = f"{screenshots_path}/Bước {step} -error: Something Bad Occured.png"
            driver.save_screenshot(screenshot_path)

def next_steps():
    driver = get_driver()
    cookies_path = f"{session_path}/cookies.json"
    cookies = driver.get_cookies()
    with open(cookies_path, 'w') as file:
        json.dump(cookies, file)

def launch_iframe():
    global driver, target_element, settings, step
    driver = get_driver()

    try:
        driver.get(url)
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        output(f"Bước {step} -Đang cố gắng xác minh xem chúng tôi đã đăng nhập chưa (hy vọng mã QR không xuất hiện).",3)
        xpath = "//canvas[@class='qr-canvas']"
        wait = WebDriverWait(driver, 5)
        wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        if settings['debugIsOn']:
            screenshot_path = f"{screenshots_path}/Bước {step} -Kiểm tra mã QR sau khi phiên tiếp tục.png"
            driver.save_screenshot(screenshot_path)
        output(f"Bước {step} -Trình điều khiển Chrome báo cáo mã QR hiển thị: Có vẻ như chúng tôi không còn đăng nhập nữa.",2)
        output(f"Bước {step} -Rất có thể bạn sẽ nhận được cảnh báo rằng không tìm thấy hộp nhập liệu trung tâm.",2)
        output(f"Bước {step} -Hệ thống sẽ cố gắng khôi phục phiên hoặc khởi động lại tập lệnh từ CLI buộc đăng nhập mới.\n",2)

    except TimeoutException:
        output(f"Bước {step} -không tìm thấy gì để hành động. Đã vượt qua bài kiểm tra mã QR.\n",3)
    increase_step()

    driver.get(url)
    WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')

    #Có một trường hợp rất khó xảy ra là cuộc trò chuyện có thể đã bị xóa.
#Trong trường hợp này, cần nhấn nút "BẮT ĐẦU" để hiển thị cửa sổ trò chuyện!
    xpath = "//button[contains(., 'START')]"
    button = move_and_click(xpath, 8, False, "kiểm tra nút bắt đầu (không nên có)", step, "visible")
    if button:
        button.click()
    increase_step()


    #Logic liên kết mới để tránh tìm và liên kết hết hạn
    if find_working_link(step):
        increase_step()
    else:
        send_start(step)
        increase_step()
        find_working_link(step)
        increase_step()

    #Bây giờ hãy chuyển sang và JS nhấp vào nút "Khởi chạy"
    xpath = "//button[contains(@class, 'popup-button') and contains(., 'Launch')]"
    button = move_and_click(xpath, 8, False, "click the 'Launch' button", step, "visible")
    if button:
        button.click()
    increase_step()

    #Xử lý cửa sổ bật lên HereWalletBot
    select_iframe(step)
    increase_step()

def click_element(xpath, timeout=30):
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            element = driver.find_element(By.XPATH, xpath)
            #Đảm bảo phần tử nằm trong khung nhìn
            driver.execute_script("arguments[0].scrollIntoView();", element)
            
            #Xóa mọi lớp phủ tiềm năng trước khi thử nhấp vào
            overlays_cleared = clear_overlays(element, step)
            if overlays_cleared is None:
                overlays_cleared = 0

            if overlays_cleared > 0:
                output(f"Step {step} - Cleared {overlays_cleared} overlay(s), retrying click...", 3)

            #Cố gắng nhấp vào phần tử
            element.click()
            return True  #Thành công khi nhấp vào phần tử
        except ElementClickInterceptedException as e:
            #Nếu vẫn bị chặn, hãy thử ẩn trực tiếp phần tử chặn
            intercepting_element = driver.execute_script(
                "var elem = arguments[0];"
                "var rect = elem.getBoundingClientRect();"
                "var x = rect.left + (rect.width / 2);"
                "var y = rect.top + (rect.height / 2);"
                "return document.elementFromPoint(x, y);", element)
            if intercepting_element:
                driver.execute_script("arguments[0].style.display = 'none';", intercepting_element)
                output(f"Step {step} - Intercepting element hidden, retrying click...", 3)
        except UnexpectedAlertPresentException:
            #Xử lý cảnh báo bất ngờ trong quá trình click
            alert = driver.switch_to.alert
            alert_text = alert.text
            alert.accept()  #Chấp nhận cảnh báo hoặc sửa đổi nếu bạn cần loại bỏ hoặc tương tác khác
            output(f"Step {step} - Unexpected alert handled: {alert_text}", 3)
        except (StaleElementReferenceException, NoSuchElementException):
            pass  #Không tìm thấy phần tử hoặc phần tử cũ, hãy thử lại
        except TimeoutException:
            output(f"Step {step} - Click timed out.", 2)
            break  #Thoát khỏi vòng lặp nếu hết thời gian
        except Exception as e:
            output(f"Step {step} - An error occurred:", 3)
            break  #Thoát khỏi vòng lặp do lỗi không mong muốn
    return False  #Trả về Sai nếu không thể nhấp vào phần tử

def apply_random_offset(unmodifiedTimer, settings, step, output):
    if settings['lowestClaimOffset'] <= settings['highestClaimOffset']:
        random_offset = random.randint(settings['lowestClaimOffset'], settings['highestClaimOffset'])
        modifiedTimer = unmodifiedTimer + random_offset
        output(f"Step {step} - Random offset applied to the wait timer of: {random_offset} minutes.", 2)
        return modifiedTimer
    return unmodifiedTimer

def full_claim():
    global driver, target_element, settings, session_path, step, random_offset
    step = "100"

    def check_daily_reward():
        action = ActionChains(driver)
        
        #Chọn liên kết 'Nhiệm vụ' và nhấp vào nó
        mission_xpath = "//p[contains(text(), 'Missions')]"
        move_and_click(mission_xpath, 10, False, "move to the missions link", step, "visible")
        success = click_element(mission_xpath)
        if success:
            output(f"Step {step} - Successfully able to click the 'Missions' link.",3)
        else:
            output(f"Step {step} - Failed to click the 'Missions' link.",3)
        
        #Chọn liên kết 'Hàng ngày' và nhấp vào nó
        daily_xpath = "//p[contains(text(), 'Daily')]"
        move_and_click(daily_xpath, 10, False, "move to the daily missions link", step, "visible")
        button = move_and_click(daily_xpath, 10, False, "move to the daily missions link", step, "visible")
        success = click_element(daily_xpath)
        if success:
            output(f"Step {step} - Successfully able to click the 'Daily Missions' link.",3)
        else:
            output(f"Step {step} - Failed to click the 'Daily Missions' link.",3)
        increase_step()
        
        #Hãy thử chọn và nhấp vào liên kết 'Xác nhận quyền sở hữu'
        claim_xpath = "//p[contains(text(), 'Claim')]"
        button = move_and_click(claim_xpath, 10, False, "move to the claim daily missions link", step, "visible")
        if button:
            driver.execute_script("arguments[0].click();", button)
        success = click_element(claim_xpath)
        if success:
            increase_step()
            output(f"Step {step} - Successfully able to click the 'Claim Daily' link.",3)
            return "Daily bonus claimed."
        
        #Kiểm tra xem thông báo 'Quay lại vào ngày mai' có hiển thị không
        come_back_tomorrow_xpath = "//p[contains(text(), 'Come back tomorrow')]"
        come_back_tomorrow_msg = move_and_click(come_back_tomorrow_xpath, 10, False, "check if the bonus is for tomorrow", step, "visible")
        if come_back_tomorrow_msg:
            increase_step()
            return "The daily bonus will be available tomorrow."
        
        #Nếu không có điều kiện nào được đáp ứng, trả về tin nhắn mặc định
        increase_step()
        return "Daily bonus status không xác định."

    launch_iframe()

    xpath = "//p[text()='Collect']"
    island_text = ""
    success = click_element(xpath)
    if success:
        output(f"Step {step} - We clicked the reward button for the Island Claim.",3)
        island_text = "Island bonus claimed. "
    increase_step()

    #Nhấp vào liên kết Lưu trữ:
    xpath = "//p[text()='Mining']"
    success = click_element(xpath)
    increase_step()

    try:
        element = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(
                (By.XPATH, "//div[contains(@class, '_balanceCon_qig4y_22')]//p[@class='_value_qig4y_16']")
            )
        )

        #Truy xuất nội dung văn bản của phần tử cân bằng
        if element is not None:
            balance_part = element.text.strip()  #Lấy nội dung văn bản và loại bỏ mọi khoảng trắng ở đầu/cuối
            output(f"Step {step} - VERT balance prior to claim: {balance_part}", 3)

    except NoSuchElementException:
        output(f"Step {step} - Element containing 'VERT Balance:' was not found.", 3)
    except Exception as e:
        print(f"Step {step} - An error occurred:", e)
    increase_step()

    wait_time_text = get_wait_time(step, "pre-claim") 
    output(f"Step {step} - Pre-Claim raw wait time text: {wait_time_text}",3)

    if wait_time_text != "Ready to collect":
        matches = re.findall(r'(\d+)([hm])', wait_time_text)
        remaining_wait_time = (sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)) + random_offset
        if remaining_wait_time < 5 or settings["forceClaim"]:
            settings['forceClaim'] = True
            output(f"Step {step} - the remaining time to claim is less than the random offset, so applying: settings['forceClaim'] = True", 3)
        else:
            remaining_wait_time = min (180, remaining_wait_time)
            output(f"STATUS: {island_text}We'll go back to sleep for {remaining_wait_time} minutes.", 1)
            return remaining_wait_time

    if wait_time_text == "không xác định":
      return 15

    try:
        output(f"Step {step} - The pre-claim wait time is : {wait_time_text} and random offset is {random_offset} minutes.",1)
        increase_step()

        if wait_time_text == "Ready to collect" or settings['forceClaim']:
            try:
                xpath = "//div[p[text()='Collect']]"
                success = click_element(xpath)
                if success:
                    output(f"Step {step} - We successfully clicked the Collect button.",2)
                else:
                    output(f"Step {step} - We failed to the Collect button.",2)

                xpath = "//p[contains(@class, '_text_16x1w_17') and text()='Claim']"
                success = click_element(xpath)
                if success:
                    output(f"Step {step} Successfully Claimed The new splash from vertus :) ", 2)
                else:
                    output(f"Step {step} Failed to click 'the newest Claim' button", 2)
                increase_step()

                time.sleep(5)

                wait_time_text = get_wait_time(step, "post-claim") 
                output(f"Step {step} - Post-Claim raw wait time text: {wait_time_text}",3)
                matches = re.findall(r'(\d+)([hm])', wait_time_text)
                total_wait_time = apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                increase_step()

                try:
                    element = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located(
                            (By.XPATH, "//div[contains(@class, '_balanceCon_qig4y_22')]//p[@class='_value_qig4y_16']")
                        )
                    )

                    #Truy xuất nội dung văn bản của phần tử cân bằng
                    if element is not None:
                        balance_part = element.text.strip()  #Lấy nội dung văn bản và loại bỏ mọi khoảng trắng ở đầu/cuối
                        output(f"Step {step} - post claim Vert BALANCE: {balance_part}", 2)

                except NoSuchElementException:
                    output(f"Step {step} - Element containing 'VERT Balance:' was not found.", 3)
                except Exception as e:
                    print(f"Step {step} - An error occurred:", e)
                increase_step()

                #Nhận phần thưởng hàng ngày
                daily_reward_text = check_daily_reward()
                increase_step()
                
                if wait_time_text == "Ready to collect":
                    output(f"TRẠNG THÁI: Đồng hồ chờ vẫn hiển thị: Đã đầy",1)
                    output(f"Step {step} - This means either the claim failed, or there is >4 minutes lag in the game.",1)
                    output(f"Step {step} - We'll check back in 1 hour to see if the claim processed and if not try again.",2)
                else:
                    output(f"STATUS: {island_text}. Successful Claim & {daily_reward_text}: Next claim in {min(60, total_wait_time)} minutes.",1)
                return min(180, total_wait_time)

            except TimeoutException:
                output(f"TRẠNG THÁI: Quá trình xác nhận quyền sở hữu đã hết thời gian: Có thể trang web bị lag? Sẽ thử lại sau một giờ.",1)
                return 60
            except Exception as e:
                output(f"TRẠNG THÁI: Đã xảy ra lỗi khi cố gắng xác nhận quyền sở hữu: {e}\nHãy đợi một giờ và thử lại",1)
                return 60

        else:
            #Nếu ví chưa sẵn sàng để nhận, hãy tính thời gian chờ dựa trên bộ đếm thời gian được cung cấp trên trang
            matches = re.findall(r'(\d+)([hm])', wait_time_text)
            if matches:
                total_time = sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)
                total_time += 1
                total_time = max(5, total_time) #Đợi ít nhất 5 phút hoặc thời gian
                output(f"Step {step} - Not Time to claim this wallet yet. Wait for {total_time} minutes until the storage is filled.",2)
                return total_time 
            else:
                output(f"Step {step} - No wait time data found? Let's check again in one hour.",2)
                return 60  #Thời gian chờ mặc định khi không tìm thấy thời gian cụ thể cho đến khi được lấp đầy.
    except Exception as e:
        output(f"Step {step} - An unexpected error occurred: {e}",1)
        return 60  #Thời gian chờ mặc định trong trường hợp xảy ra lỗi không mong muốn

def monitor_element(xpath, timeout=8):
    end_time = time.time() + timeout
    first_time = True
    while time.time() < end_time:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            #Gỡ lỗi: Xuất ra số phần tử được tìm thấy
            if first_time:
                output(f"Step {step} - Found {len(elements)} elements with XPath: {xpath}", 3)
                first_time = False

            #Kiểm tra xem có tìm thấy phần tử nào không
            if elements:
                #Lấy nội dung văn bản của phần tử div có liên quan đầu tiên
                for element in elements:
                    if element.text.strip() != "":
                        cleaned_text = element.text.replace('\n', ' ').replace('\r', ' ').strip()
                        return cleaned_text

        except (StaleElementReferenceException, TimeoutException, NoSuchElementException):
            pass
        except Exception as e:
            output(f"Đã xảy ra lỗi: {e}", 3)
    return "không xác định"
        
def get_wait_time(step_number="108", beforeAfter="pre-claim", max_attempts=2):
    for attempt in range(1, max_attempts + 1):
        try:
            xpath = "//p[contains(@class, 'descInfo')][1]"
            move_and_click(xpath, 10, False, f"get the {beforeAfter} wait timer", step, "visible")
            wait_time_element = monitor_element(xpath,10)
            
            #Kiểm tra xem wait_time_element có phải là None không và trả về văn bản của nó
            if wait_time_element is not None:
                return wait_time_element
            else:
                output(f"Step {step_number} - Attempt {attempt}: Wait time element not found. Clicking the 'Storage' link and retrying...", 3)
                storage_xpath = "//h4[text()='Storage']"
                move_and_click(storage_xpath, 30, True, "click the 'storage' link", f"{step_number} recheck", "clickable")
                output(f"Step {step_number} - Attempted to select storage again...", 3)

        except TimeoutException:
            if attempt < max_attempts:  #Đã thử không thành công nhưng vẫn thử lại
                output(f"Step {step_number} - Attempt {attempt}: Wait time element not found. Clicking the 'Storage' link and retrying...", 3)
                storage_xpath = "//h4[text()='Storage']"
                move_and_click(storage_xpath, 30, True, "click the 'storage' link", f"{step_number} recheck", "clickable")
            else:  #Không còn lần thử lại nào sau lần thất bại đầu tiên
                output(f"Step {step_number} - Attempt {attempt}: Wait time element not found.", 3)

        except Exception as e:
            output(f"Step {step_number} - An error occurred on attempt {attempt}: {e}", 3)

    #Nếu mọi nỗ lực đều thất bại
    return "không xác định"

def clear_screen():
    #Cố gắng xóa màn hình sau khi nhập cụm từ gốc hoặc số điện thoại di động.
#Cho cửa sổ
    if os.name == 'nt':
        os.system('cls')
    #Dành cho macOS và Linux
    else:
        os.system('clear')

def select_iframe(old_step):
    global driver, screenshots_path, settings, step
    output(f"Step {step} - Attempting to switch to the app's iFrame...",2)

    try:
        wait = WebDriverWait(driver, 20)
        popup_body = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "popup-body")))
        iframe = popup_body.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe)
        output(f"Step {step} - Was successfully able to switch to the app's iFrame.\n",3)

        if settings['debugIsOn']:
            screenshot_path = f"{screenshots_path}/{step}-iframe-switched.png"
            driver.save_screenshot(screenshot_path)

    except TimeoutException:
        output(f"Step {step} - Failed to find or switch to the iframe within the timeout period.\n",3)
        if settings['debugIsOn']:
            screenshot_path = f"{screenshots_path}/{step}-iframe-timeout.png"
            driver.save_screenshot(screenshot_path)
    except Exception as e:
        output(f"Step {step} - An error occurred while attempting to switch to the iframe: {e}\n",3)
        if settings['debugIsOn']:
            screenshot_pat,h = f"{screenshots_path}/{step}-iframe-error.png"
            driver.save_screenshot(screenshot_path)

def find_working_link(old_step):
    global driver, screenshots_path, settings, step
    output(f"Step {step} - Attempting to open a link for the app...",2)

    start_app_xpath = "//div[@class='reply-markup-row']//span[contains(text(),'Open app') or contains(text(), 'Play')]"
    try:
        start_app_buttons = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.XPATH, start_app_xpath)))
        clicked = False

        for button in reversed(start_app_buttons):
            actions = ActionChains(driver)
            actions.move_to_element(button).pause(0.2)
            try:
                if settings['debugIsOn']:
                    driver.save_screenshot(f"{screenshots_path}/{step} - Find working link.png".format(screenshots_path))
                actions.perform()
                driver.execute_script("arguments[0].click();", button)
                clicked = True
                break
            except StaleElementReferenceException:
                continue
            except ElementClickInterceptedException:
                continue

        if not clicked:
            output(f"Step {step} - None of the 'Open Wallet' buttons were clickable.\n",1)
            if settings['debugIsOn']:
                screenshot_path = f"{screenshots_path}/{step}-no-clickable-button.png"
                driver.save_screenshot(screenshot_path)
            return False
        else:
            output(f"Step {step} - Successfully able to open a link for the app..\n",3)
            if settings['debugIsOn']:
                screenshot_path = f"{screenshots_path}/{step}-app-opened.png"
                driver.save_screenshot(screenshot_path)
            return True

    except TimeoutException:
        output(f"Step {step} - Failed to find the 'Open Wallet' button within the expected timeframe.\n",1)
        if settings['debugIsOn']:
            screenshot_path = f"{screenshots_path}/{step}-timeout-finding-button.png"
            driver.save_screenshot(screenshot_path)
        return False
    except Exception as e:
        output(f"Step {step} - An error occurred while trying to open the app: {e}\n",1)
        if settings['debugIsOn']:
            screenshot_path = f"{screenshots_path}/{step}-unexpected-error-opening-app.png"
            driver.save_screenshot(screenshot_path)
        return False


def send_start(old_step):
    global driver, screenshots_path, backup_path, settings, step
    xpath = "//div[contains(@class, 'input-message-container')]/div[contains(@class, 'input-message-input')][1]"
    
    def attempt_send_start():
        global backup_path
        chat_input = move_and_click(xpath, 5, False, "find the chat window/message input box", step, "present")
        if chat_input:
            increase_step()
            output(f"Step {step} - Attempting to send the '/start' command...",2)
            chat_input.send_keys("/start")
            chat_input.send_keys(Keys.RETURN)
            output(f"Step {step} - Successfully sent the '/start' command.\n",3)
            if settings['debugIsOn']:
                screenshot_path = f"{screenshots_path}/{step}-sent-start.png"
                driver.save_screenshot(screenshot_path)
            return True
        else:
            output(f"Step {step} - Failed to find the message input box.\n",1)
            return False

    if not attempt_send_start():
        #Cố gắng không thành công, hãy thử khôi phục từ bản sao lưu và thử lại
        output(f"Step {step} - Attempting to restore from backup and retry.\n",2)
        if restore_from_backup(backup_path):
            if not attempt_send_start():  #Thử lại sau khi khôi phục bản sao lưu
                output(f"Step {step} - Retried after restoring backup, but still failed to send the '/start' command.\n",1)
        else:
            output(f"Step {step} - Backup restoration failed or backup directory does not exist.\n",1)

def restore_from_backup(path):
    global step, session_path
    if os.path.exists(path):
        try:
            quit_driver()
            shutil.rmtree(session_path)
            shutil.copytree(path, session_path, dirs_exist_ok=True)
            driver = get_driver()
            driver.get(url)
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            output(f"Step {step} - Backup restored successfully.",2)
            return True
        except Exception as e:
            output(f"Step {step} - Error restoring backup: {e}\n",1)
            return False
    else:
        output(f"Step {step} - Backup directory does not exist.\n",1)
        return False

def move_and_click(xpath, wait_time, click, action_description, old_step, expectedCondition):
    global driver, screenshots_path, settings, step
    target_element = None

    def timer():
        return random.randint(1, 3) / 10

    def offset():
        return random.randint(1, 5)

    def handle_alert():
        try:
            while True:
                alert = driver.switch_to.alert
                alert_text = alert.text
                alert.accept()  #hoặc Alert.dismiss() nếu bạn cần loại bỏ nó
                output(f"STATUS: Alert handled: {alert_text}", 1)
        except:
            pass

    output(f"Step {step} - Attempting to {action_description}...", 2)

    try:
        wait = WebDriverWait(driver, wait_time)
        #Kiểm tra và chuẩn bị phần tử dựa trên điều kiện dự kiến
        if expectedCondition == "visible":
            target_element = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
        elif expectedCondition == "present":
            target_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        elif expectedCondition == "invisible":
            wait.until(EC.invisibility_of_element_located((By.XPATH, xpath)))
            return None  #Hoàn trả sớm vì không có yếu tố nào để tương tác
        elif expectedCondition == "clickable":
            target_element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))

        #Kiểm tra xem target_element có được tìm thấy không
        if target_element is None:
            output(f"Step {step} - The element was not found for {action_description}.", 2)
            return None

        #Trước khi tương tác, hãy kiểm tra và xóa lớp phủ nếu cần nhấp chuột hoặc cần hiển thị
        if expectedCondition in ["visible", "clickable"]:
            clear_overlays(target_element, step)

        #Thực hiện các hành động nếu tìm thấy phần tử và yêu cầu nhấp chuột
        if target_element:
            if expectedCondition == "clickable":
                actions = ActionChains(driver)
                actions.move_by_offset(0, 0 - offset()) \
                        .pause(timer()) \
                        .move_by_offset(0, offset()) \
                        .pause(timer()) \
                        .move_to_element(target_element) \
                        .pause(timer()) \
                        .perform()
                output(f"Step {step} - Successfully moved to the element using ActionChains.", 3)
            if click:
                click_element(xpath, wait_time)
        
        #Liên tục xử lý các cảnh báo trong suốt quá trình
        handle_alert()

        return target_element

    except UnexpectedAlertPresentException as e:
        handle_alert()

    except TimeoutException:
        output(f"Step {step} - Timeout while trying to {action_description}.", 3)
        if settings['debugIsOn']:
            #Chụp nguồn trang và lưu nó vào một tập tin
            page_source = driver.page_source
            with open(f"{screenshots_path}/{step}_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logs = driver.get_log("browser")
            with open(f"{screenshots_path}/{step}_browser_console_logs.txt", "w", encoding="utf-8") as f:
                for log in logs:
                    f.write(f"{log['level']}: {log['message']}\n")

    except StaleElementReferenceException:
        output(f"Step {step} - StaleElementReferenceException caught for {action_description}.", 2)

    except Exception as e:
        output(f"Step {step} - An error occurred while trying to {action_description}, or maybe we got a success message.", 1)

    finally:
        #Kiểm tra và xử lý các cảnh báo còn sót lại trước khi kết thúc
        handle_alert()
        if settings['debugIsOn']:
            time.sleep(5)
            screenshot_path = f"{screenshots_path}/{step}-{action_description}.png"
            driver.save_screenshot(screenshot_path)
        return target_element

def clear_overlays(target_element, step):
    try:
        #Lấy vị trí của phần tử mục tiêu
        element_location = target_element.location_once_scrolled_into_view
        overlays = driver.find_elements(By.XPATH, "//*[contains(@style,'position: absolute') or contains(@style,'position: fixed')]")
        overlays_cleared = 0
        for overlay in overlays:
            overlay_rect = overlay.rect
            #Kiểm tra xem lớp phủ có bao phủ phần tử đích không
            if (overlay_rect['x'] <= element_location['x'] <= overlay_rect['x'] + overlay_rect['width'] and
                overlay_rect['y'] <= element_location['y'] <= overlay_rect['y'] + overlay_rect['height']):
                driver.execute_script("arguments[0].style.display = 'none';", overlay)
                overlays_cleared += 1
        output(f"Step {step} - Removed {overlays_cleared} overlay(s) covering the target.", 3)
        return overlays_cleared
    except Exception as e:
        output(f"Step {step} - An error occurred while trying to clear overlays: {e}", 1)
        return 0

def validate_seed_phrase():
    #Hãy lấy cụm từ hạt giống mà người dùng đã nhập và thực hiện xác thực cơ bản
    while True:
        #Nhắc người dùng về cụm từ gốc của họ
        if settings['hideSensitiveInput']:
            seed_phrase = getpass.getpass(f"Step {step} - Please enter your 12-word seed phrase (your input is hidden): ")
        else:
            seed_phrase = input(f"Step {step} - Please enter your 12-word seed phrase (your input is visible): ")
        try:
            if not seed_phrase:
              raise ValueError(f"Step {step} - Seed phrase cannot be empty.")

            words = seed_phrase.split()
            if len(words) != 12:
                raise ValueError(f"Step {step} - Seed phrase must contain exactly 12 words.")

            pattern = r"^[a-z ]+$"
            if not all(re.match(pattern, word) for word in words):
                raise ValueError(f"Step {step} - Seed phrase can only contain lowercase letters and spaces.")
            return seed_phrase  #Trả lại nếu hợp lệ

        except ValueError as e:
            output(f"Error: {e}",1)

#Bắt đầu quy trình PM2 mới
def start_pm2_app(script_path, app_name, session_name):
    interpreter_path = "venv/bin/python3"
    command = f"NODE_NO_WARNINGS=1 pm2 start {script_path} --name {app_name} --interpreter {interpreter_path} --watch {script_path} -- {session_name}"
    subprocess.run(command, shell=True, check=True)

#Liệt kê tất cả các quy trình PM2
def save_pm2():
    command = f"NODE_NO_WARNINGS=1 pm2 save"
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    print(result.stdout)

def backup_telegram():
    global session_path, step

    #Hỏi người dùng xem họ có muốn sao lưu thư mục Telegram của mình không
    backup_prompt = input("Would you like to backup your Telegram directory? (Y/n): ").strip().lower()
    if backup_prompt == 'n':
        output(f"Step {step} - Backup skipped by user choice.", 3)
        return

    #Yêu cầu người dùng đặt tên tệp tùy chỉnh
    custom_filename = input("Enter a custom filename for the backup (leave blank for default): ").strip()

    #Xác định đường dẫn đích sao lưu
    if custom_filename:
        backup_directory = os.path.join(os.path.dirname(session_path), f"Telegram:{custom_filename}")
    else:
        backup_directory = os.path.join(os.path.dirname(session_path), "Telegram")

    try:
        #Đảm bảo thư mục sao lưu tồn tại và sao chép nội dung
        if not os.path.exists(backup_directory):
            os.makedirs(backup_directory)
        shutil.copytree(session_path, backup_directory, dirs_exist_ok=True)
        output(f"Step {step} - We backed up the session data in case of a later crash!", 3)
    except Exception as e:
        output(f"Step {step} - Oops, we weren't able to make a backup of the session data! Error: {e}", 1)

def main():
    global session_path, settings, step
    if not settings["forceNewSession"]:
        load_settings()
    cookies_path = os.path.join(session_path, 'cookies.json')
    if os.path.exists(cookies_path) and not settings['forceNewSession']:
        output("Resuming the previous session...",2)
    else:
        telegram_backup_dirs = [d for d in os.listdir(os.path.dirname(session_path)) if d.startswith("Telegram")]
        if telegram_backup_dirs:
            print("Previous Telegram login sessions found. Pressing <enter> will select the account numbered '1':")
            for i, dir_name in enumerate(telegram_backup_dirs):
                print(f"{i + 1}. {dir_name}")
    
            user_input = input("Enter the number of the session you want to restore, or 'n' to create a new session: ").strip().lower()
    
            if user_input == 'n':
                log_into_telegram()
                quit_driver()
                backup_telegram()
            elif user_input.isdigit() and 0 < int(user_input) <= len(telegram_backup_dirs):
                restore_from_backup(os.path.join(os.path.dirname(session_path), telegram_backup_dirs[int(user_input) - 1]))
            else:
                restore_from_backup(os.path.join(os.path.dirname(session_path), telegram_backup_dirs[0]))  #Mặc định cho phiên đầu tiên

        else:
            log_into_telegram()
            quit_driver()
            backup_telegram()

        next_steps()
        quit_driver()

        try:
            shutil.copytree(session_path, backup_path, dirs_exist_ok=True)
            output("We backed up the session data in case of a later crash!",3)
        except Exception as e:
            output("Oops, we weren't able to make a backup of the session data! Error:", 1)

        pm2_session = session_path.replace("./selenium/", "")
        output(f"You could add the new/updated session to PM use: pm2 start {script} --interpreter venv/bin/python3 --name {pm2_session} -- {pm2_session}",1)
        user_choice = input("Enter 'y' to continue to 'claim' function, 'e' to exit, 'a' or <enter> to automatically add to PM2: ").lower()

        if user_choice == "e":
            output("Exiting script. You can resume the process later.", 1)
            sys.exit()
        elif user_choice == "a" or not user_choice:
            start_pm2_app(script, pm2_session, pm2_session)
            user_choice = input("Should we save your PM2 processes? (Y/n): ").lower()
            if user_choice == "y" or not user_choice:
                save_pm2()
            output(f"You can now watch the session log into PM2 with: pm2 logs {pm2_session}", 2)
            sys.exit()

    while True:
        manage_session()
        wait_time = full_claim()

        if os.path.exists(status_file_path):
            with open(status_file_path, "r+") as file:
                status = json.load(file)
                if session_path in status:
                    del status[session_path]
                    file.seek(0)
                    json.dump(status, file)
                    file.truncate()
                    output(f"Session released: {session_path}",3)

        quit_driver()
                
        now = datetime.now()
        next_claim_time = now + timedelta(minutes=wait_time)
        this_claim_str = now.strftime("%d %B - %H:%M")
        next_claim_time_str = next_claim_time.strftime("%d %B - %H:%M")
        output(f"{this_claim_str} | Need to wait until {next_claim_time_str} before the next claim attempt. Approximately {wait_time} minutes.", 1)
        if settings["forceClaim"]:
            settings["forceClaim"] = False

        while wait_time > 0:
            this_wait = min(wait_time, 15)
            now = datetime.now()
            timestamp = now.strftime("%H:%M")
            output(f"[{timestamp}] Waiting for {this_wait} more minutes...",3)
            time.sleep(this_wait * 60)  #Chuyển đổi phút thành giây
            wait_time -= this_wait
            if wait_time > 0:
                output(f"Updated wait time: {wait_time} minutes left.",3)


if __name__ == "__main__":
    main()
