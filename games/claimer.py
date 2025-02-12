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
from selenium.webdriver.chrome.service import Service as ChromeService

import requests

class Claimer():

    def __init__(self):
        self.initialize_settings()
        self.load_settings()
        self.random_offset = random.randint(self.settings['lowestClaimOffset'], self.settings['highestClaimOffset'])
        print(f"Initialising the {self.prefix} Wallet Auto-claim Python Script - Good Luck!")

        self.imported_seedphrase = None

        #Cập nhật cài đặt dựa trên đầu vào của người dùng
        if len(sys.argv) > 1:
            user_input = sys.argv[1]  #Nhận ID phiên từ đối số dòng lệnh
            self.wallet_id = user_input
            self.output(f"Session ID provided: {user_input}", 2)
            
            #Kiểm tra an toàn đối số thứ hai
            if len(sys.argv) > 2 and sys.argv[2] == "reset":
                self.settings['forceNewSession'] = True

            #Kiểm tra cờ --seed-phrase và xác thực nó
            if '--seed-phrase' in sys.argv:
                seed_index = sys.argv.index('--seed-phrase') + 1
                if seed_index < len(sys.argv):
                    self.seed_phrase = ' '.join(sys.argv[seed_index:])
                    seed_words = self.seed_phrase.split()
                    if len(seed_words) == 12:
                        self.output(f"Seed phrase accepted:", 2)
                        self.imported_seedphrase = self.seed_phrase
                    else:
                        self.output("Invalid seed phrase. Ignoring.", 2)
                else:
                    self.output("No seed phrase provided after --seed-phrase flag. Ignoring.", 2)
        else:
            self.output("\nCurrent settings:", 1)
            for key, value in self.settings.items():
                self.output(f"{key}: {value}", 1)
            user_input = input("\nShould we update our settings? (Default:<enter> / Yes = y): ").strip().lower()
            if user_input == "y":
                self.update_settings()
            user_input = self.get_session_id()
            self.wallet_id = user_input

        self.session_path = "./selenium/{}".format(self.wallet_id)
        os.makedirs(self.session_path, exist_ok=True)
        self.screenshots_path = "./screenshots/{}".format(self.wallet_id)
        os.makedirs(self.screenshots_path, exist_ok=True)
        self.backup_path = "./backups/{}".format(self.wallet_id)
        os.makedirs(self.backup_path, exist_ok=True)
        self.step = "01"

        #Xác định đường dẫn cơ sở của chúng tôi để gỡ lỗi ảnh chụp màn hình
        self.screenshot_base = os.path.join(self.screenshots_path, "screenshot")

        if self.settings["useProxy"] and self.settings["proxyAddress"] == "http://127.0.0.1:8080":
            self.run_http_proxy()
        elif self.forceLocalProxy:
            self.run_http_proxy()
            self.output("Use of the built-in proxy is force on for this game.", 2)
        else:
            self.output("Proxy disabled in settings.", 2)

    def initialize_settings(self):
        self.settings_file = "variables.txt"
        self.status_file_path = "status.txt"
        self.start_app_xpath = None
        self.settings = {}
        self.driver = None
        self.target_element = None
        self.random_offset = 0
        self.seed_phrase = None
        self.wallet_id = ""
        self.script = "default_script.py"
        self.prefix = "Default:"

    def run(self):
        if not self.settings["forceNewSession"]:
            self.load_settings()
        cookies_path = os.path.join(self.session_path, 'cookies.json')
        if os.path.exists(cookies_path) and not self.settings['forceNewSession']:
            self.output("Resuming the previous session...", 2)
        else:
            telegram_backup_dirs = [d for d in os.listdir(os.path.dirname(self.session_path)) if d.startswith("Telegram")]
            if telegram_backup_dirs:
                print("Previous Telegram login sessions found. Pressing <enter> will select the account numbered '1':")
                for i, dir_name in enumerate(telegram_backup_dirs):
                    print(f"{i + 1}. {dir_name}")

                user_input = input("Enter the number of the session you want to restore, or 'n' to create a new session: ").strip().lower()

                if user_input == 'n':
                    self.log_into_telegram(self.wallet_id)
                    self.quit_driver()
                    self.backup_telegram()
                elif user_input.isdigit() and 0 < int(user_input) <= len(telegram_backup_dirs):
                    self.restore_from_backup(os.path.join(os.path.dirname(self.session_path), telegram_backup_dirs[int(user_input) - 1]))
                else:
                    self.restore_from_backup(os.path.join(os.path.dirname(self.session_path), telegram_backup_dirs[0]))  #Mặc định cho phiên đầu tiên

            else:
                self.log_into_telegram(self.wallet_id)
                self.quit_driver()
                self.backup_telegram()

            self.next_steps()
            self.quit_driver()

            try:
                shutil.copytree(self.session_path, self.backup_path, dirs_exist_ok=True)
                self.output("We backed up the session data in case of a later crash!", 3)
            except Exception as e:
                self.output(f"Oops, we weren't able to make a backup of the session data! Error: {e}", 1)

            pm2_session = self.session_path.replace("./selenium/", "")
            self.output(f"You could add the new/updated session to PM use: pm2 start {self.script} --interpreter venv/bin/python3 --name {pm2_session} -- {pm2_session}", 1)
            user_choice = input("Enter 'y' to continue to 'claim' function, 'e' to exit, 'a' or <enter> to automatically add to PM2: ").lower()

            if user_choice == "e":
                self.output("Exiting script. You can resume the process later.", 1)
                sys.exit()
            elif user_choice == "a" or not user_choice:
                self.start_pm2_app(self.script, pm2_session, pm2_session)
                user_choice = input("Should we save your PM2 processes? (Y/n): ").lower()
                if user_choice == "y" or not user_choice:
                    self.save_pm2()
                self.output(f"You can now watch the session log into PM2 with: pm2 logs {pm2_session}", 2)
                sys.exit()

        while True:
            self.manage_session()
            wait_time = self.full_claim()

            if os.path.exists(self.status_file_path):
                with open(self.status_file_path, "r+") as file:
                    status = json.load(file)
                    if self.session_path in status:
                        del status[self.session_path]
                        file.seek(0)
                        json.dump(status, file)
                        file.truncate()
                        self.output(f"Session released: {self.session_path}", 3)

            self.quit_driver()

            now = datetime.now()
            #Kiểm tra xem wait_time có phải là số không, giả sử 30
            if not isinstance(wait_time, (int, float)):
                wait_time = 30
            next_claim_time = now + timedelta(minutes=wait_time)
            this_claim_str = now.strftime("%d %B - %H:%M")
            next_claim_time_str = next_claim_time.strftime("%d %B - %H:%M")
            self.output(f"{this_claim_str} | Need to wait until {next_claim_time_str} before the next claim attempt. Approximately {wait_time} minutes.", 1)
            if self.settings["forceClaim"]:
                self.settings["forceClaim"] = False

            while wait_time > 0:
                this_wait = min(wait_time, 15)
                now = datetime.now()
                timestamp = now.strftime("%H:%M")
                self.output(f"[{timestamp}] Waiting for {this_wait} more minutes...", 3)
                time.sleep(this_wait * 60)  #Chuyển đổi phút thành giây
                wait_time -= this_wait
                if wait_time > 0:
                    self.output(f"Updated wait time: {wait_time} minutes left.", 3)

    def load_settings(self):
        default_settings = {
            "forceClaim": False,
            "debugIsOn": False,
            "hideSensitiveInput": True,
            "screenshotQRCode": True,
            "maxSessions": 1,
            "verboseLevel": 2,
            "telegramVerboseLevel": 0,
            "lowestClaimOffset": 0,
            "highestClaimOffset": 15,
            "forceNewSession": False,
            "useProxy": False,
            "proxyAddress": "http://127.0.0.1:8080",
            "requestUserAgent": False,
            "telegramBotToken": "", 
            "telegramBotChatId": ""
        }

        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as f:
                loaded_settings = json.load(f)
            #Lọc các cài đặt không sử dụng từ các phiên bản trước
            self.settings = {k: loaded_settings.get(k, v) for k, v in default_settings.items()}
            self.output("Settings loaded successfully.", 3)
        else:
            self.settings = default_settings
            self.save_settings()

    def save_settings(self):
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f)
        self.output("Settings saved successfully.", 3)

    def update_settings(self):

        def update_setting(setting_key, message, default_value):
            current_value = self.settings.get(setting_key, default_value)
            response = input(f"\n{message} (Y/N, press Enter to keep current [{current_value}]): ").strip().lower()
            if response == "y":
                self.settings[setting_key] = True
            elif response == "n":
                self.settings[setting_key] = False

        update_setting("forceClaim", "Shall we force a claim on first run? Does not wait for the timer to be filled", self.settings["forceClaim"])
        update_setting("debugIsOn", "Should we enable debugging? This will save screenshots in your local drive", self.settings["debugIsOn"])
        update_setting("hideSensitiveInput", "Should we hide sensitive input? Your phone number and seed phrase will not be visible on the screen", self.settings["hideSensitiveInput"])
        update_setting("screenshotQRCode", "Shall we allow log in by QR code? The alternative is by phone number and one-time password", self.settings["screenshotQRCode"])

        try:
            new_max_sessions = int(input(f"\nEnter the number of max concurrent claim sessions. Additional claims will queue until a session slot is free.\n(current: {self.settings['maxSessions']}): "))
            self.settings["maxSessions"] = new_max_sessions
        except ValueError:
            self.output("Number of sessions remains unchanged.", 1)

        try:
            new_verbose_level = int(input("\nEnter the number for how much information you want displaying in the script console.\n 3 = all messages, 2 = claim steps, 1 = minimal steps\n(current: {}): ".format(self.settings['verboseLevel'])))
            if 1 <= new_verbose_level <= 3:
                self.settings["verboseLevel"] = new_verbose_level
                self.output("Verbose level updated successfully.", 2)
            else:
                self.output("Verbose level remains unchanged.", 2)
        except ValueError:
            self.output("Verbose level remains unchanged.", 2)

        try:
            new_telegram_verbose_level = int(input("\nHow much information to show in the Telegram bot? (3 = all messages, 2 = claim steps, 1 = minimal steps, 0 = none)\n(current: {}): ".format(self.settings['telegramVerboseLevel'])))
            if 0 <= new_telegram_verbose_level <= 3:
                self.settings["telegramVerboseLevel"] = new_telegram_verbose_level
                self.output("Telegram verbose level updated successfully.", 2)
            else:
                self.output("Telegram verbose level remains unchanged.", 2)
        except ValueError:
            self.output("Telegram verbose level remains unchanged.", 2)

        try:
            new_lowest_offset = int(input("\nEnter the lowest possible offset for the claim timer (valid values are -30 to +30 minutes)\n(current: {}): ".format(self.settings['lowestClaimOffset'])))
            if -30 <= new_lowest_offset <= 30:
                self.settings["lowestClaimOffset"] = new_lowest_offset
                self.output("Lowest claim offset updated successfully.", 2)
            else:
                self.output("Invalid range for lowest claim offset. Please enter a value between -30 and +30.", 2)
        except ValueError:
            self.output("Lowest claim offset remains unchanged.", 2)

        try:
            new_highest_offset = int(input("\nEnter the highest possible offset for the claim timer (valid values are 0 to 60 minutes)\n(current: {}): ".format(self.settings['highestClaimOffset'])))
            if 0 <= new_highest_offset <= 60:
                self.settings["highestClaimOffset"] = new_highest_offset
                self.output("Highest claim offset updated successfully.", 2)
            else:
                self.output("Invalid range for highest claim offset. Please enter a value between 0 and 60.", 2)
        except ValueError:
            self.output("Highest claim offset remains unchanged.", 2)

        if self.settings["lowestClaimOffset"] > self.settings["highestClaimOffset"]:
            self.settings["lowestClaimOffset"] = self.settings["highestClaimOffset"]
            self.output("Adjusted lowest claim offset to match the highest as it was greater.", 2)

        update_setting("useProxy", "Use Proxy?", self.settings["useProxy"])

        if self.settings["useProxy"]:
            proxy_address = input(f"\nEnter the Proxy IP address and port (current: {self.settings['proxyAddress']}): ").strip()
            if proxy_address:
                self.settings["proxyAddress"] = proxy_address

        update_setting("requestUserAgent", "Shall we collect a User Agent during setup?: ", self.settings["requestUserAgent"])

        #Thu thập mã thông báo Bot Telegram
        new_telegram_bot_token = input(f"\nEnter the Telegram Bot Token (current: {self.settings['telegramBotToken']}): ").strip()
        if new_telegram_bot_token:
            self.settings["telegramBotToken"] = new_telegram_bot_token

        self.save_settings()

        update_setting("forceNewSession", "Overwrite existing session and Force New Login? Use this if your saved session has crashed\nOne-Time only (setting not saved): ", self.settings["forceNewSession"])

        self.output("\nRevised settings:", 1)
        for key, value in self.settings.items():
            self.output(f"{key}: {value}", 1)
        self.output("", 1)

    def output(self, string, level=2):
        if self.settings['verboseLevel'] >= level:
            print(string)
        if self.settings['telegramBotToken'] and not self.settings['telegramBotChatId']:
            try:
                self.settings['telegramBotChatId'] = self.get_telegram_bot_chat_id()
                self.save_settings()  #Lưu cài đặt sau khi nhận được ID trò chuyện
            except ValueError as e:
                pass
                #print(f"Lỗi tìm nạp ID trò chuyện Telegram: {e}")
        if self.settings['telegramBotChatId'] and self.wallet_id and self.settings['telegramVerboseLevel'] >= level:
            self.send_message(string)

    def get_telegram_bot_chat_id(self):
        url = f"https://api.telegram.org/bot{self.settings['telegramBotToken']}/getUpdates"
        response = requests.get(url).json()
        #print(response) # Thêm dòng này để in toàn bộ phản hồi (Đã nhận xét để có kết quả rõ ràng hơn)
        if 'result' in response and len(response['result']) > 0:
            return response['result'][0]['message']['chat']['id']
        else:
            raise ValueError("No messages found in response")

    def send_message(self, string):
        try:
            if self.settings['telegramBotChatId'] == "":
                self.settings['telegramBotChatId'] = self.get_telegram_bot_chat_id()

            message = f"{self.wallet_id}: {string}"
            url = f"https://api.telegram.org/bot{self.settings['telegramBotToken']}/sendMessage?chat_id={self.settings['telegramBotChatId']}&text={message}"
            response = requests.get(url).json()
            #print(response) # Thao tác này sẽ gửi tin nhắn và in phản hồi (Đã nhận xét để có kết quả rõ ràng hơn)
            if not response.get("ok"):
                raise ValueError(f"Failed to send message: {response}")
        except ValueError as e:
            print(f"Error: {e}")

    def increase_step(self):
        step_int = int(self.step) + 1
        self.step = f"{step_int:02}"

    def update_settings(self):

        def update_setting(setting_key, message, default_value):
            current_value = self.settings.get(setting_key, default_value)
            response = input(f"\n{message} (Y/N, press Enter to keep current [{current_value}]): ").strip().lower()
            if response == "y":
                self.settings[setting_key] = True
            elif response == "n":
                self.settings[setting_key] = False

        update_setting("forceClaim", "Shall we force a claim on first run? Does not wait for the timer to be filled", self.settings["forceClaim"])
        update_setting("debugIsOn", "Should we enable debugging? This will save screenshots in your local drive", self.settings["debugIsOn"])
        update_setting("hideSensitiveInput", "Should we hide sensitive input? Your phone number and seed phrase will not be visible on the screen", self.settings["hideSensitiveInput"])
        update_setting("screenshotQRCode", "Shall we allow log in by QR code? The alternative is by phone number and one-time password", self.settings["screenshotQRCode"])

        try:
            new_max_sessions = int(input(f"\nEnter the number of max concurrent claim sessions. Additional claims will queue until a session slot is free.\n(current: {self.settings['maxSessions']}): "))
            self.settings["maxSessions"] = new_max_sessions
        except ValueError:
            self.output("Number of sessions remains unchanged.", 1)

        try:
            new_verbose_level = int(input("\nEnter the number for how much information you want displaying in the console.\n 3 = all messages, 2 = claim steps, 1 = minimal steps\n(current: {}): ".format(self.settings['verboseLevel'])))
            if 1 <= new_verbose_level <= 3:
                self.settings["verboseLevel"] = new_verbose_level
                self.output("Verbose level updated successfully.", 2)
            else:
                self.output("Verbose level remains unchanged.", 2)
        except ValueError:
            self.output("Verbose level remains unchanged.", 2)

        try:
            new_telegram_verbose_level = int(input("\nEnter the Telegram verbose level (3 = all messages, 2 = claim steps, 1 = minimal steps)\n(current: {}): ".format(self.settings['telegramVerboseLevel'])))
            if 1 <= new_telegram_verbose_level <= 3:
                self.settings["telegramVerboseLevel"] = new_telegram_verbose_level
                self.output("Telegram verbose level updated successfully.", 2)
            else:
                self.output("Telegram verbose level remains unchanged.", 2)
        except ValueError:
            self.output("Telegram verbose level remains unchanged.", 2)


        try:
            new_lowest_offset = int(input("\nEnter the lowest possible offset for the claim timer (valid values are -30 to +30 minutes)\n(current: {}): ".format(self.settings['lowestClaimOffset'])))
            if -30 <= new_lowest_offset <= 30:
                self.settings["lowestClaimOffset"] = new_lowest_offset
                self.output("Lowest claim offset updated successfully.", 2)
            else:
                self.output("Invalid range for lowest claim offset. Please enter a value between -30 and +30.", 2)
        except ValueError:
            self.output("Lowest claim offset remains unchanged.", 2)

        try:
            new_highest_offset = int(input("\nEnter the highest possible offset for the claim timer (valid values are 0 to 60 minutes)\n(current: {}): ".format(self.settings['highestClaimOffset'])))
            if 0 <= new_highest_offset <= 60:
                self.settings["highestClaimOffset"] = new_highest_offset
                self.output("Highest claim offset updated successfully.", 2)
            else:
                self.output("Invalid range for highest claim offset. Please enter a value between 0 and 60.", 2)
        except ValueError:
            self.output("Highest claim offset remains unchanged.", 2)

        if self.settings["lowestClaimOffset"] > self.settings["highestClaimOffset"]:
            self.settings["lowestClaimOffset"] = self.settings["highestClaimOffset"]
            self.output("Adjusted lowest claim offset to match the highest as it was greater.", 2)

        update_setting("useProxy", "Use Proxy?", self.settings["useProxy"])

        if self.settings["useProxy"]:
            proxy_address = input(f"\nEnter the Proxy IP address and port (current: {self.settings['proxyAddress']}): ").strip()
            if proxy_address:
                self.settings["proxyAddress"] = proxy_address

        update_setting("requestUserAgent", "Shall we collect a User Agent during setup?: ", self.settings["requestUserAgent"])

        #Thu thập mã thông báo Bot Telegram
        new_telegram_bot_token = input(f"\nEnter the Telegram Bot Token (current: {self.settings['telegramBotToken']}): ").strip()
        if new_telegram_bot_token:
            self.settings["telegramBotToken"] = new_telegram_bot_token

        self.save_settings()

        update_setting("forceNewSession", "Overwrite existing session and Force New Login? Use this if your saved session has crashed\nOne-Time only (setting not saved): ", self.settings["forceNewSession"])

        self.output("\nRevised settings:", 1)
        for key, value in self.settings.items():
            self.output(f"{key}: {value}", 1)
        self.output("", 1)

    def get_session_id(self):
        """Prompts the user for a session ID or determines the next sequential ID based on a 'Wallet' prefix.

        Returns:
            str: The entered session ID or the automatically generated sequential ID.
        """
        self.output(f"Your session will be prefixed with: {self.prefix}", 1)
        user_input = input("Enter your unique Session Name here, or hit <enter> for the next sequential wallet: ").strip()

        #Đặt thư mục lưu trữ các thư mục phiên
        screenshots_dir = "./screenshots/"

        #Đảm bảo thư mục tồn tại để tránh FileNotFoundError
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        #Liệt kê nội dung của thư mục
        try:
            dir_contents = os.listdir(screenshots_dir)
        except Exception as e:
            self.output(f"Error accessing the directory: {e}", 1)
            return None  #hoặc xử lý lỗi theo cách khác
#Lọc các thư mục có tiền tố 'Wallet' và trích xuất các phần số
        wallet_dirs = [int(dir_name.replace(self.prefix + 'Wallet', ''))
                    for dir_name in dir_contents
                    if dir_name.startswith(self.prefix + 'Wallet') and dir_name[len(self.prefix) + 6:].isdigit()]

        #Tính ID ví tiếp theo
        next_wallet_id = max(wallet_dirs) + 1 if wallet_dirs else 1

        #Sử dụng ID ví tuần tự tiếp theo nếu không có thông tin đầu vào nào của người dùng được cung cấp
        if not user_input:
            user_input = f"Wallet{next_wallet_id}"  #Đảm bảo ID đầy đủ được đặt tiền tố chính xác

        return self.prefix+user_input

    def prompt_user_agent(self):
        print (f"Step {self.step} - Please enter the User-Agent string you wish to use or press enter for default.")
        user_agent = input(f"Step {self.step} - User-Agent: ").strip()
        return user_agent

    def set_cookies(self):
        if not (self.forceRequestUserAgent or self.settings["requestUserAgent"]):
            cookies_path = f"{self.session_path}/cookies.json"
            cookies = self.driver.get_cookies()
            with open(cookies_path, 'w') as file:
                json.dump(cookies, file)
        else:
            user_agent = self.prompt_user_agent()
            cookies_path = f"{self.session_path}/cookies.json"
            cookies = self.driver.get_cookies()
            cookies.append({"name": "user_agent", "value": user_agent})  #Lưu tác nhân người dùng vào cookie
            with open(cookies_path, 'w') as file:
                json.dump(cookies, file)

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument(f"user-data-dir={self.session_path}")
        chrome_options.add_argument("--headless")  #Đảm bảo tính năng không đầu được bật
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        #Cố gắng tải tác nhân người dùng từ cookie
        try:
            cookies_path = f"{self.session_path}/cookies.json"
            with open(cookies_path, 'r') as file:
                cookies = json.load(file)
                user_agent_cookie = next((cookie for cookie in cookies if cookie["name"] == "user_agent"), None)
                if user_agent_cookie and user_agent_cookie["value"]:
                    user_agent = user_agent_cookie["value"]
                    self.output(f"Using saved user agent: {user_agent}", 2)
                else:
                    user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/124.0.2478.50 Version/17.0 Mobile/15E148 Safari/604.1"
                    self.output("No user agent found, using default.", 2)
        except FileNotFoundError:
            user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/124.0.2478.50 Version/17.0 Mobile/15E148 Safari/604.1"
            self.output("Cookies file not found, using default user agent.", 2)

        chrome_options.add_argument(f"user-agent={user_agent}")

        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        if self.settings["useProxy"]:
            proxy_server = self.settings["proxyAddress"]
            chrome_options.add_argument(f"--proxy-server={proxy_server}")

        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--test-type")

        chromedriver_path = shutil.which("chromedriver")
        if chromedriver_path is None:
            self.output("ChromeDriver not found in PATH. Please ensure it is installed.", 1)
            exit(1)

        try:
            service = Service(chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            return self.driver
        except Exception as e:
            self.output(f"Initial ChromeDriver setup may have failed: {e}", 1)
            self.output("Please ensure you have the correct ChromeDriver version for your system.", 1)
            exit(1)

    def run_http_proxy(self):
        proxy_lock_file = "./start_proxy.txt"
        max_wait_time = 15 * 60  #15 phút
        wait_interval = 5  #5 giây
        start_time = time.time()
        message_displayed = False

        while os.path.exists(proxy_lock_file) and (time.time() - start_time) < max_wait_time:
            if not message_displayed:
                self.output("Proxy is already running. Waiting for it to free up...", 2)
                message_displayed = True
            time.sleep(wait_interval)

        if os.path.exists(proxy_lock_file):
            self.output("Max wait time elapsed. Proceeding to run the proxy.", 2)

        with open(proxy_lock_file, "w") as lock_file:
            lock_file.write(f"Proxy started at: {time.ctime()}\n")

        try:
            subprocess.run(['./launch.sh', 'enable-proxy'], check=True)
            self.output("http-proxy started successfully.", 2)
        except subprocess.CalledProcessError as e:
            self.output(f"Failed to start http-proxy: {e}", 1)
        finally:
            os.remove(proxy_lock_file)

    def get_driver(self):
        if self.driver is None:  #Kiểm tra xem trình điều khiển có cần được khởi tạo không
            self.manage_session()  #Đảm bảo chúng ta có thể bắt đầu một phiên
            self.driver = self.setup_driver()
            self.output("\nCHROME DRIVER INITIALISED: Try not to exit the script before it detaches.",2)
        return self.driver

    def quit_driver(self):
        if self.driver:
            self.driver.quit()
            self.output("\nCHROME DRIVER DETACHED: It is now safe to exit the script.",2)
            self.driver = None
            self.release_session()  #Đánh dấu phiên là đã đóng

    def manage_session(self):
        current_session = self.session_path
        current_timestamp = int(time.time())
        session_started = False
        new_message = True
        output_priority = 2

        while True:
            try:
                with open(self.status_file_path, "r+") as file:
                    flock(file, LOCK_EX)
                    status = json.load(file)

                    #Dọn dẹp các phiên hết hạn
                    for session_id, timestamp in list(status.items()):
                        if current_timestamp - timestamp > 300:  #5 phút
                            del status[session_id]
                            self.output(f"Removed expired session: {session_id}", 3)

                    #Kiểm tra các vị trí có sẵn, loại trừ phiên hiện tại khỏi số lượng
                    active_sessions = {k: v for k, v in status.items() if k != current_session}
                    if len(active_sessions) < self.settings['maxSessions']:
                        status[current_session] = current_timestamp
                        file.seek(0)
                        json.dump(status, file)
                        file.truncate()
                        self.output(f"Session started: {current_session} in {self.status_file_path}", 3)
                        flock(file, LOCK_UN)
                        session_started = True
                        break
                    flock(file, LOCK_UN)

                if not session_started:
                    self.output(f"Waiting for slot. Current sessions: {len(active_sessions)}/{self.settings['maxSessions']}", output_priority)
                    if new_message:
                        new_message = False
                        output_priority = 3
                    time.sleep(random.randint(5, 15))
                else:
                    break

            except FileNotFoundError:
                #Tạo tập tin nếu nó không tồn tại
                with open(self.status_file_path, "w") as file:
                    flock(file, LOCK_EX)
                    json.dump({}, file)
                    flock(file, LOCK_UN)
            except json.decoder.JSONDecodeError:
                #Xử lý JSON trống hoặc bị hỏng
                with open(self.status_file_path, "w") as file:
                    flock(file, LOCK_EX)
                    self.output("Corrupted status file. Resetting...", 3)
                    json.dump({}, file)
                    flock(file, LOCK_UN)

    def release_session(self):
        current_session = self.session_path
        current_timestamp = int(time.time())

        with open(self.status_file_path, "r+") as file:
            flock(file, LOCK_EX)
            status = json.load(file)
            if current_session in status:
                del status[current_session]
                file.seek(0)
                json.dump(status, file)
                file.truncate()
            flock(file, LOCK_UN)
            self.output(f"Session released: {current_session}", 3)
    
    def log_into_telegram(self, user_input=None):

        self.step = "01"

        #Kiểm tra và tạo lại thư mục
        self.session_path = f"./selenium/{user_input}"
        if os.path.exists(self.session_path):
            shutil.rmtree(self.session_path)
        os.makedirs(self.session_path, exist_ok=True)

        self.screenshots_path = f"./screenshots/{user_input}"
        if os.path.exists(self.screenshots_path):
            shutil.rmtree(self.screenshots_path)
        os.makedirs(self.screenshots_path, exist_ok=True)

        self.backup_path = f"./backups/{user_input}"
        if os.path.exists(self.backup_path):
            shutil.rmtree(self.backup_path)
        os.makedirs(self.backup_path, exist_ok=True)

        def visible_QR_code():
            max_attempts = 5
            attempt_count = 0
            last_url = "not a url"  #Trình giữ chỗ cho URL mã QR được phát hiện gần đây nhất

            xpath = "//canvas[@class='qr-canvas']"
            self.driver.get(self.url)
            wait = WebDriverWait(self.driver, 30)
            self.output(f"Step {self.step} - Waiting for the first QR code - may take up to 30 seconds.", 1)
            self.increase_step()
            QR_code = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))

            if not QR_code:
                return False

            wait = WebDriverWait(self.driver, 2)

            while attempt_count < max_attempts:
                try:
                    QR_code = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
                    QR_code.screenshot(f"{self.screenshots_path}/Step {self.step} - Initial QR code.png")
                    image = Image.open(f"{self.screenshots_path}/Step {self.step} - Initial QR code.png")
                    decoded_objects = decode(image)
                    if decoded_objects:
                        this_url = decoded_objects[0].data.decode('utf-8')
                        if this_url != last_url:
                            last_url = this_url  #Cập nhật URL nhìn thấy lần cuối
                            attempt_count += 1
                            self.output("*** Important: Having @game-telegram-autobot open in your Telegram App might stop this script from logging in! ***\n", 2)
                            self.output(f"Step {self.step} - Our screenshot path is {self.screenshots_path}\n", 1)
                            self.output(f"Step {self.step} - Generating screenshot {attempt_count} of {max_attempts}\n", 2)
                            qrcode_terminal.draw(this_url)
                        if attempt_count >= max_attempts:
                            self.output(f"Step {self.step} - Max attempts reached with no new QR code.", 1)
                            return False
                        time.sleep(0.5)  #Chờ trước lần kiểm tra tiếp theo
                    else:
                        time.sleep(0.5)  #Không có mã QR nào được giải mã, hãy đợi trước khi thử lại
                except TimeoutException:
                    self.output(f"Step {self.step} - QR Code is no longer visible.", 2)
                    return True  #Cho biết mã QR đã được quét hoặc biến mất
        
            self.output(f"Step {self.step} - Failed to generate a valid QR code after multiple attempts.", 1)
            return False  #Nếu vòng lặp hoàn tất mà không quét thành công

        self.driver = self.get_driver()
    
        #Phương pháp mã QR
        if self.settings['screenshotQRCode']:
            try:
                while True:
                    if visible_QR_code():  #Không tìm thấy mã QR
                        self.test_for_2fa()
                        return  #Thoát hoàn toàn chức năng
#Nếu chúng ta đến đây nghĩa là mã QR vẫn còn:
                    choice = input(f"\nStep {self.step} - QR Code still present. Retry (r) with a new QR code or switch to the OTP method (enter): ")
                    print("")
                    if choice.lower() == 'r':
                        visible_QR_code()
                    else:
                        break

            except TimeoutException:
                self.output(f"Step {self.step} - Canvas not found: Restart the script and retry the QR Code or switch to the OTP method.", 1)

        #Phương thức đăng nhập OTP
        self.increase_step()
        self.output(f"Step {self.step} - Initiating the One-Time Password (OTP) method...\n",1)
        self.driver.get(self.url)
        xpath = "//button[contains(@class, 'btn-primary') and contains(., 'Log in by phone Number')]"
        self.move_and_click(xpath, 30, True, "switch to log in by phone number", self.step, "visible")
        self.increase_step()

        #Lựa chọn mã quốc gia
        xpath = "//div[contains(@class, 'input-field-input')]"
        self.target_element = self.move_and_click(xpath, 30, True, "update user's country", self.step, "visible")
        if not self.target_element:
            self.output(f"Step {self.step} - Failed to find country input field.", 1)
            return

        user_input = input(f"Step {self.step} - Please enter your Country Name as it appears in the Telegram list: ").strip()
        self.target_element.send_keys(user_input)
        self.target_element.send_keys(Keys.RETURN)
        self.increase_step()

        #Nhập số điện thoại
        xpath = "//div[contains(@class, 'input-field-input') and @inputmode='decimal']"
        self.target_element = self.move_and_click(xpath, 30, True, "request user's phone number", self.step, "visible")
        if not self.target_element:
            self.output(f"Step {self.step} - Failed to find phone number input field.", 1)
            return
    
        def validate_phone_number(phone):
            #Regex để xác thực số điện thoại quốc tế không có số 0 đứng đầu và thường dài từ 7 đến 15 chữ số
            pattern = re.compile(r"^[1-9][0-9]{6,14}$")
            return pattern.match(phone)

        while True:
            if self.settings['hideSensitiveInput']:
                user_phone = getpass.getpass(f"Step {self.step} - Please enter your phone number without leading 0 (hidden input): ")
            else:
                user_phone = input(f"Step {self.step} - Please enter your phone number without leading 0 (visible input): ")
    
            if validate_phone_number(user_phone):
                self.output(f"Step {self.step} - Valid phone number entered.",3)
                break
            else:
                self.output(f"Step {self.step} - Invalid phone number, must be 7 to 15 digits long and without leading 0.",1)
        self.target_element.send_keys(user_phone)
        self.increase_step()

        #Đợi nút "Tiếp theo" có thể nhấp được và nhấp vào nút đó
        xpath = "//button//span[contains(text(), 'Next')]"
        self.move_and_click(xpath, 15, True, "click next to proceed to OTP entry", self.step, "visible")
        self.increase_step()

        try:
            #Cố gắng xác định vị trí và tương tác với trường OTP
            wait = WebDriverWait(self.driver, 20)
            if self.settings['debugIsOn']:
                time.sleep(3)
                self.driver.save_screenshot(f"{self.screenshots_path}/Step {self.step} - Ready_for_OTP.png")
            password = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='tel']")))
            otp = input(f"Step {self.step} - What is the Telegram OTP from your app? ")
            password.click()
            password.send_keys(otp)
            self.output(f"Step {self.step} - Let's try to log in using your Telegram OTP.\n",3)
            self.increase_step()

        except TimeoutException:
            #Kiểm tra bộ nhớ ngoại tuyến
            xpath = "//button[contains(text(), 'STORAGE_OFFLINE')]"
            self.move_and_click(xpath, 10, True, "check for 'STORAGE_OFFLINE'", self.step, "visible")
            if self.target_element:
                self.output(f"Step {self.step} - ***Progress is blocked by a 'STORAGE_OFFLINE' button",1)
                self.output(f"Step {self.step} - If you are re-usi,ng an old Wallet session; try to delete or create a new session.",1)
                found_error = True
            #Kiểm tra chờ lũ
            xpath = "//button[contains(text(), 'FLOOD_WAIT')]"
            self.move_and_click(xpath, 10, True, "check for 'FLOOD_WAIT'", self.step, "visible")
            if self.target_element:
                self.output(f"Step {self.step} - ***Progress is blocked by a 'FLOOD_WAIT' button", 1)
                self.output(f"Step {self.step} - You need to wait for the specified number of seconds before retrying.", 1)
                self.output(f"Step {self.step} - {self.target_element.text}")
                found_error = True
            if not found_error:
                self.output(f"Step {self.step} - Selenium was unable to interact with the OTP screen for an không xác định reason.")

        except Exception as e:  #Bắt bất kỳ lỗi không mong muốn nào khác
            self.output(f"Step {self.step} - Login failed. Error: {e}", 1) 
            if self.settings['debugIsOn']:
                self.driver.save_screenshot(f"{self.screenshots_path}/Step {self.step} - error_Something_Occured.png")

        self.increase_step()
        self.test_for_2fa()

        if self.settings['debugIsOn']:
            time.sleep(3)
            self.driver.save_screenshot(f"{self.screenshots_path}/Step {self.step} - After_Entering_OTP.png")

    def test_for_2fa(self):
        try:
            self.increase_step()
            WebDriverWait(self.driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            xpath = "//input[@type='password' and contains(@class, 'input-field-input')]"
            fa_input = self.move_and_click(xpath, 15, False, "check for 2FA requirement (will timeout if you don't have 2FA)", self.step, "present")
        
            if fa_input:
                if self.settings['hideSensitiveInput']:
                    tg_password = getpass.getpass(f"Step {self.step} - Enter your Telegram 2FA password: ")
                else:
                    tg_password = input(f"Step {self.step} - Enter your Telegram 2FA password: ")
                fa_input.send_keys(tg_password + Keys.RETURN)
                self.output(f"Step {self.step} - 2FA password sent.\n", 3)
                self.output(f"Step {self.step} - Checking if the 2FA password is correct.\n", 2)
            
                xpath = "//*[contains(text(), 'Incorrect password')]"
                try:
                    incorrect_password = WebDriverWait(self.driver, 3).until(EC.visibility_of_element_located((By.XPATH, xpath)))
                    self.output(f"Step {self.step} - 2FA password is marked as incorrect by Telegram - check your debug screenshot if active.", 1)
                    if self.settings['debugIsOn']:
                        screenshot_path = f"{self.screenshots_path}/Step {self.step} - Incorrect 2FA Password.png"
                        self.driver.save_screenshot(screenshot_path)
                    self.quit_driver()
                    sys.exit()  #Thoát nếu phát hiện mật khẩu sai
                except TimeoutException:
                    pass

                self.output(f"Step {self.step} - No password error found.", 3)
                xpath = "//input[@type='password' and contains(@class, 'input-field-input')]"
                fa_input = self.move_and_click(xpath, 5, False, "final check to make sure we are correctly logged in", self.step, "present")
                if fa_input:
                    self.output(f"Step {self.step} - 2FA password entry is still showing, check your debug screenshots for further information.\n", 1)
                    sys.exit()
                self.output(f"Step {self.step} - 2FA password check appears to have passed OK.\n", 3)
            else:
                self.output(f"Step {self.step} - 2FA input field not found.\n", 1)

        except TimeoutException:
            #Không tìm thấy trường 2FA
            self.output(f"Step {self.step} - Two-factor Authorization not required.\n", 3)

        except Exception as e:  #Bắt bất kỳ lỗi không mong muốn nào khác
            self.output(f"Step {self.step} - Login failed. 2FA Error - you'll probably need to restart the script: {e}", 1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/Step {self.step} - error_Something_Bad_Occurred.png"
                self.driver.save_screenshot(screenshot_path)

    def next_steps(self):
        #Phải GHI ĐÈ chức năng này trong lớp con
        self.output("Function 'next-steps' - Not defined (Need override in child class) \n", 1)

    def launch_iframe(self):
        self.driver = self.get_driver()

        try:
            self.driver.get(self.url)
            WebDriverWait(self.driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            self.output(f"Step {self.step} - Attempting to verify if we are logged in (hopefully QR code is not present).", 3)
            xpath = "//canvas[@class='qr-canvas']"
            wait = WebDriverWait(self.driver, 5)
            wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/Step {self.step} - Test QR code after session is resumed.png"
                self.driver.save_screenshot(screenshot_path)
            self.output(f"Step {self.step} - Chrome driver reports the QR code is visible: It appears we are no longer logged in.", 2)
            self.output(f"Step {self.step} - Most likely you will get a warning that the central input box is not found.", 2)
            self.output(f"Step {self.step} - System will try to restore session, or restart the script from CLI to force a fresh log in.\n", 2)

        except TimeoutException:
            self.output(f"Step {self.step} - nothing found to action. The QR code test passed.\n", 3)
        self.increase_step()

        self.driver.get(self.url)
        WebDriverWait(self.driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')

        #Có một trường hợp rất khó xảy ra là cuộc trò chuyện có thể đã bị xóa.
#Trong trường hợp này, cần nhấn nút "BẮT ĐẦU" để hiển thị cửa sổ trò chuyện!
        xpath = "//button[contains(., 'START')]"
        button = self.move_and_click(xpath, 3, False, "check for the start button (should not be present)", self.step, "clickable")
        if button:
            button.click()
        self.increase_step()

        #Logic liên kết mới để tránh tìm thấy một liên kết đã hết hạn
        if self.find_working_link(self.step):
            self.increase_step()
        else:
            self.send_start(self.step)
            self.increase_step()
            self.find_working_link(self.step)
            self.increase_step()

        #Bây giờ hãy chuyển sang và JS nhấp vào nút "Khởi chạy"
        xpath = "//button[contains(@class, 'popup-button') and contains(., 'Launch')]"
        button = self.move_and_click(xpath, 8, False, "click the 'Launch' button (probably not present)", self.step, "clickable")
        if button:
            button.click()
        self.increase_step()

        #Xử lý cửa sổ bật lên HereWalletBot
        self.select_iframe(self.step)
        self.increase_step()


    def full_claim(self):
        #Phải GHI ĐÈ chức năng này trong lớp con
        self.output("Function 'full_claim' - Not defined (Need override in child class) \n", 1)

    def get_balance(self,claimed=False):
        #Phải GHI ĐÈ chức năng này trong lớp con
        self.output("Function 'get_balance' - Not defined (Need override in child class) \n", 1)

    def clear_screen(self):
        #Cố gắng xóa màn hình sau khi nhập cụm từ gốc hoặc số điện thoại di động.
#Cho cửa sổ
        if os.name == 'nt':
            os.system('cls')
        #Dành cho macOS và Linux
        else:
            os.system('clear')

    def select_iframe(self, old_step):
        self.output(f"Step {self.step} - Attempting to switch to the app's iFrame...",2)

        try:
            wait = WebDriverWait(self.driver, 20)
            popup_body = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "popup-body")))
            iframe = popup_body.find_element(By.TAG_NAME, "iframe")
            self.driver.switch_to.frame(iframe)
            self.output(f"Step {self.step} - Was successfully able to switch to the app's iFrame.\n",3)

            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-iframe-switched.png"
                self.driver.save_screenshot(screenshot_path)

        except TimeoutException:
            self.output(f"Bước {self.step} -Không tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.\n",3)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-iframe-timeout.png"
                self.driver.save_screenshot(screenshot_path)
        except Exception as e:
            self.output(f"Step {self.step} - An error occurred while attempting to switch to the iframe: {e}\n",3)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-iframe-error.png"
                self.driver.save_screenshot(screenshot_path)

    def send_start(self, old_step):
        xpath = "//div[contains(@class, 'input-message-container')]/div[contains(@class, 'input-message-input')][1]"
        
        def attempt_send_start():
            chat_input = self.move_and_click(xpath, 5, False, "find the chat window/message input box", self.step, "present")
            if chat_input:
                self.increase_step()
                self.output(f"Step {self.step} - Attempting to send the '/start' command...",2)
                chat_input.send_keys("/start")
                chat_input.send_keys(Keys.RETURN)
                self.output(f"Step {self.step} - Successfully sent the '/start' command.\n",3)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-sent-start.png"
                    self.driver.save_screenshot(screenshot_path)
                return True
            else:
                self.output(f"Step {self.step} - Failed to find the message input box.\n",1)
                return False

        if not attempt_send_start():
            #Cố gắng không thành công, hãy thử khôi phục từ bản sao lưu và thử lại
            self.output(f"Step {self.step} - Attempting to restore from backup and retry.\n",2)
            if self.restore_from_backup(self.backup_path):
                if not attempt_send_start():  #Thử lại sau khi khôi phục bản sao lưu
                    self.output(f"Step {self.step} - Retried after restoring backup, but still failed to send the '/start' command.\n",1)
            else:
                self.output(f"Step {self.step} - Backup restoration failed or backup directory does not exist.\n",1)

    def restore_from_backup(self, path):
        if os.path.exists(path):
            try:
                self.quit_driver()
                shutil.rmtree(self.session_path)
                shutil.copytree(path, self.session_path, dirs_exist_ok=True)
                self.driver = self.get_driver()
                self.driver.get(self.url)
                WebDriverWait(self.driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')
                self.output(f"Step {self.step} - Backup restored successfully.",2)
                return True
            except Exception as e:
                self.output(f"Step {self.step} - Error restoring backup: {e}\n",1)
                return False
        else:
            self.output(f"Step {self.step} - Backup directory does not exist.\n",1)
            return False

    def move_and_click(self, xpath, wait_time, click, action_description, old_step, expectedCondition):
        def timer():
            return random.randint(1, 3) / 10

        self.output(f"Step {self.step} - Attempting to {action_description}... [{xpath}]", 2)

        wait = WebDriverWait(self.driver, wait_time)
        target_element = None
        for attempt in range(5):  #Thử lại vòng lặp để xử lý StaleElementReferenceException
            try:
                if expectedCondition == "visible":
                    target_element = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
                elif expectedCondition == "present":
                    target_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                elif expectedCondition == "invisible":
                    wait.until(EC.invisibility_of_element_located((By.XPATH, xpath)))
                    if self.settings['debugIsOn']:
                        screenshot_path = f"{self.screenshots_path}/{self.step}_{action_description}_invisible.png"
                        self.driver.save_screenshot(screenshot_path)
                        self.output(f"Ảnh chụp màn hình đã được lưu vào {screenshot_path}", 3)
                    return None
                elif expectedCondition == "clickable":
                    target_element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))

                if target_element is None:
                    self.output(f"Bước {self.step} -Không tìm thấy phần tử cho {action_description}.", 2)
                    return None

                actions = ActionChains(self.driver)
                actions.move_to_element(target_element).pause(timer()).perform()

                self.driver.execute_script("""
                    var elem = arguments[0];
                    var rect = elem.getBoundingClientRect();
                    var isVisible = (
                        rect.top >= 0 &&
                        rect.left >= 0 &&
                        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                    );
                    if (!isVisible) {
                        elem.scrollIntoView({block: 'center'});
                    }
                """, target_element)

                is_in_viewport = self.driver.execute_script("""
                    var elem = arguments[0], box = elem.getBoundingClientRect();
                    return (box.top >= 0 && box.left >= 0 &&
                            box.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                            box.right <= (window.innerWidth || document.documentElement.clientWidth));
                """, target_element)

                if not is_in_viewport:
                    self.output(f"Step {self.step} - Element still out of bounds after moving with ActionChains and JavaScript scrolling.", 2)
                    continue

                if click or expectedCondition in ["visible", "clickable"]:
                    self.clear_overlays(target_element, self.step)

                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}_{action_description}_before_click.png"
                    self.driver.save_screenshot(screenshot_path)

                if click:
                    if self.click_element(xpath, action_description=action_description):
                        self.output(f"Step {self.step} - Successfully clicked {action_description}.", 3)
                        return target_element
                else:
                    return target_element

            except StaleElementReferenceException:
                self.output(f"Step {self.step} - StaleElementReferenceException caught, retrying attempt {attempt + 1} for {action_description}.", 2)
            except TimeoutException:
                self.output(f"Bước {self.step} -Hết thời gian chờ trong khi cố gắng{action_description}.", 3)
                self.debug_information(action_description)
                break
            except Exception as e:
                self.output(f"Bước {self.step} -Đã xảy ra lỗi khi cố gắng {action_description}: {e}", 1)
                self.debug_information(action_description)
                break

        return target_element

    def click_element(self, xpath, timeout=30, action_description=""):
        end_time = time.time() + timeout
        if self.settings['debugIsOn']:
            screenshot_path = f"{self.screenshots_path}/{self.step}_{action_description}_click_element.png"
            self.driver.save_screenshot(screenshot_path)
        while time.time() < end_time:
            try:
                element = self.driver.find_element(By.XPATH, xpath)
                actions = ActionChains(self.driver)
                actions.move_to_element(element).perform()

                self.driver.execute_script("""
                    var elem = arguments[0];
                    var rect = elem.getBoundingClientRect();
                    var isVisible = (
                        rect.top >= 0 &&
                        rect.left >= 0 &&
                        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                    );
                    if (!isVisible) {
                        elem.scrollIntoView({block: 'center'});
                    }
                """, element)

                overlays_cleared = self.clear_overlays(element, self.step)
                if overlays_cleared > 0:
                    self.output(f"Step {self.step} - Cleared {overlays_cleared} overlay(s), retrying click...", 3)

                actions.click(element).perform()
                return True
            except ElementClickInterceptedException as e:
                intercepting_element = self.driver.execute_script(
                    "var elem = arguments[0];"
                    "var rect = elem.getBoundingClientRect();"
                    "var x = rect.left + (rect.width / 2);"
                    "var y = rect.top + (rect.height / 2);"
                    "return document.elementFromPoint(x, y);", element)
                if intercepting_element:
                    self.driver.execute_script("arguments[0].style.display = 'none';", intercepting_element)
                    self.output(f"Step {self.step} - Intercepting element hidden, retrying click...", 3)
            except UnexpectedAlertPresentException:
                alert = self.driver.switch_to.alert
                alert.accept()
                self.output(f"Step {self.step} - Unexpected alert handled.", 3)
            except (StaleElementReferenceException, NoSuchElementException):
                pass
            except TimeoutException:
                self.output(f"Bước {self.step} -Đã hết thời gian Click .", 2)
                break
            except Exception as e:
                self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}", 3)
                break
        return False

    def clear_overlays(self, target_element, step):
        try:
            element_location = target_element.location_once_scrolled_into_view
            overlays = self.driver.find_elements(By.XPATH, "//*[contains(@style,'position: absolute') or contains(@style,'position: fixed')]")
            overlays_cleared = 0
            for overlay in overlays:
                overlay_rect = overlay.rect
                if (overlay_rect['x'] <= element_location['x'] <= overlay_rect['x'] + overlay_rect['width'] and
                    overlay_rect['y'] <= element_location['y'] <= overlay_rect['y'] + overlay_rect['height']):
                    self.driver.execute_script("arguments[0].style.display = 'none';", overlay)
                    overlays_cleared += 1
            self.output(f"Step {step} - Removed {overlays_cleared} overlay(s) covering the target.", 3)
            return overlays_cleared
        except Exception as e:
            self.output(f"Step {step} - An error occurred while trying to clear overlays: {e}", 1)
            return 0

    def monitor_element(self, xpath, timeout=8, action_description=""):
        end_time = time.time() + timeout
        first_time = True
        if self.settings['debugIsOn']:
            screenshot_path = f"{self.screenshots_path}/{self.step}_{action_description}_monitor_element.png"
            self.driver.save_screenshot(screenshot_path)
        while time.time() < end_time:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                if first_time:
                    self.output(f"Bước {self.step} -Đã tìm thấy phần tử {len(elements)} với XPath: {xpath} for {action_description}", 3)
                    first_time = False

                texts = [element.text.replace('\n', ' ').replace('\r', ' ').strip() for element in elements if element.text.strip()]
                if texts:
                    return ' '.join(texts)
            except (StaleElementReferenceException, TimeoutException, NoSuchElementException):
                pass
            except Exception as e:
                self.output(f"Đã xảy ra lỗi: {e}", 3)
                if self.settings['debugIsOn']:
                    self.debug_information(action_description, "monitor_element_error")
                return "không xác định"
        return "không xác định"

    def debug_information(self, action_description, error_type="error"):
        #Kiểm tra xem "không" có xuất hiện trong action_description được đặt trong ngoặc không
        if re.search(r'\(.*?not.*?\)', action_description, re.IGNORECASE):
            #Bỏ qua việc gỡ lỗi nếu điều kiện được đáp ứng
            return

        if self.settings['debugIsOn']:
            #Lưu nguồn trang HTML bị lỗi
            page_source = self.driver.page_source
            with open(f"{self.screenshots_path}/{self.step}_{action_description}_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)

            #Lưu nhật ký bảng điều khiển trình duyệt do lỗi
            logs = self.driver.get_log("browser")
            with open(f"{self.screenshots_path}/{self.step}_{action_description}_browser_console_logs.txt", "w", encoding="utf-8") as f:
                for log in logs:
                    f.write(f"{log['level']}: {log['message']}\n")

    def find_working_link(self, old_step):

        start_app_xpath = self.start_app_xpath
        self.output(f"Step {self.step} - Attempting to open a link for the app: {start_app_xpath}...", 2)

        try:
            #Đợi sự hiện diện của tất cả các phần tử được định vị bởi XPath đã chỉ định với thời gian chờ kéo dài
            start_app_buttons = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, start_app_xpath))
            )
            clicked = False

            if not start_app_buttons:
                self.output(f"Step {self.step} - No buttons found with XPath: {start_app_xpath}\n", 1)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-no-buttons-found.png"
                    self.driver.save_screenshot(screenshot_path)
                return False

            #Lặp lại các nút theo thứ tự ngược lại
            for button in reversed(start_app_buttons):
                actions = ActionChains(self.driver)
                actions.move_to_element(button).pause(0.2)
                try:
                    #Lưu ảnh chụp màn hình nếu tính năng gỡ lỗi được bật
                    if self.settings['debugIsOn']:
                        self.driver.save_screenshot(f"{self.screenshots_path}/{self.step} - Find working link.png")
                    #Thực hiện các hành động và nhấp vào nút bằng JavaScript
                    actions.perform()
                    self.driver.execute_script("arguments[0].click();", button)
                    clicked = True
                    break
                except (StaleElementReferenceException, ElementClickInterceptedException):
                    self.output(f"Step {self.step} - Button click intercepted or stale, trying next button.", 2)
                    continue

            #Kiểm tra xem nút đã được nhấp thành công chưa
            if not clicked:
                self.output(f"Bước {self.step} -Không có nút 'Mở ví' nào có thể nhấp được.\n", 1)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-no-clickable-button.png"
                    self.driver.save_screenshot(screenshot_path)
                return False
            else:
                self.output(f"Bước {self.step} -Có thể mở liên kết cho ứng dụng thành công..\n", 3)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-app-opened.png"
                    self.driver.save_screenshot(screenshot_path)
                return True

        except TimeoutException:
            self.output(f"Step {self.step} - Failed to find the 'Open Wallet' button within the expected timeframe.\n", 1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-timeout-finding-button.png"
                self.driver.save_screenshot(screenshot_path)
            return False
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi khi cố gắng open the app: {e}\n", 1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-unexpected-error-opening-app.png"
                self.driver.save_screenshot(screenshot_path)
            return False

    def validate_seed_phrase(self):
        #Hãy lấy cụm từ hạt giống mà người dùng đã nhập và thực hiện xác thực cơ bản
        while True:
            #Nhắc người dùng về cụm từ gốc của họ
            if self.settings['hideSensitiveInput']:
                self.seed_phrase = getpass.getpass(f"Step {self.step} - Please enter your 12-word seed phrase (your input is hidden): ")
            else:
                self.seed_phrase = input(f"Step {self.step} - Please enter your 12-word seed phrase (your input is visible): ")
            try:
                if not self.seed_phrase:
                    raise ValueError(f"Step {self.step} - Seed phrase cannot be empty.")

                words = self.seed_phrase.split()
                if len(words) != 12:
                    raise ValueError(f"Step {self.step} - Seed phrase must contain exactly 12 words.")

                pattern = r"^[a-z ]+$"
                if not all(re.match(pattern, word) for word in words):
                    raise ValueError(f"Step {self.step} - Seed phrase can only contain lowercase letters and spaces.")
                return self.seed_phrase  #Trả lại nếu hợp lệ

            except ValueError as e:
                self.output(f"Error: {e}",1)

    #Bắt đầu quy trình PM2 mới
    def start_pm2_app(self, script_path, app_name, session_name):
        interpreter_path = "venv/bin/python3"
        command = f"NODE_NO_WARNINGS=1 pm2 start {script_path} --name {app_name} --interpreter {interpreter_path} --watch {script_path} -- {session_name}"
        subprocess.run(command, shell=True, check=True)

    #Lưu quy trình PM2 mới
    def save_pm2(self):
        command = f"NODE_NO_WARNINGS=1 pm2 save"
        result = subprocess.run(command, shell=True, text=True, capture_output=True)
        print(result.stdout)
        
    def backup_telegram(self):

        #Hỏi người dùng xem họ có muốn sao lưu thư mục Telegram của mình không
        backup_prompt = input("Would you like to backup your Telegram directory? (Y/n): ").strip().lower()
        if backup_prompt == 'n':
            self.output(f"Step {self.step} - Backup skipped by user choice.", 3)
            return

        #Yêu cầu người dùng đặt tên tệp tùy chỉnh
        custom_filename = input("Enter a custom filename for the backup (leave blank for default): ").strip()

        #Xác định đường dẫn đích sao lưu
        if custom_filename:
            backup_directory = os.path.join(os.path.dirname(self.session_path), f"Telegram:{custom_filename}")
        else:
            backup_directory = os.path.join(os.path.dirname(self.session_path), "Telegram")

        try:
            #Đảm bảo thư mục sao lưu tồn tại và sao chép nội dung
            if not os.path.exists(backup_directory):
                os.makedirs(backup_directory)
            shutil.copytree(self.session_path, backup_directory, dirs_exist_ok=True)
            self.output(f"Step {self.step} - We backed up the session data in case of a later crash!", 3)
        except Exception as e:
            self.output(f"Step {self.step} - Oops, we weren't able to make a backup of the session data! Error: {e}", 1)

    def get_seed_phrase_from_file(self, screenshots_path):
        seed_file_path = os.path.join(screenshots_path, 'seed.txt')
        if os.path.exists(seed_file_path):
            with open(seed_file_path, 'r') as file:
                return file.read().strip()
        return None

    def show_time(self, time):
        hours = int(time / 60)
        minutes = time % 60
        if hours > 0:
            return f"{hours} hours and {minutes} minutes"
        return f"{minutes} minutes"

    def strip_html_and_non_numeric(self, text):
        """Remove HTML tags and keep only numeric characters and decimal points."""
        text = self.strip_html(text)
        text = self.strip_non_numeric(text)
        return text
    
    def strip_html(self, text):
        """Remove HTML tags."""
        clean = re.compile('<.*?>')
        return clean.sub('', text)
    
    def strip_non_numeric(self, text):
        """Keep only numeric characters and decimal points."""
        return re.sub(r'[^0-9.]', '', text)
    
    def apply_random_offset(self, unmodifiedTimer):
        if self.settings['lowestClaimOffset'] <= self.settings['highestClaimOffset']:
            self.random_offset = random.randint(self.settings['lowestClaimOffset'], self.settings['highestClaimOffset'])
            modifiedTimer = unmodifiedTimer + self.random_offset
            self.output(f"Step {self.step} - Random offset applied to the wait timer of: {self.random_offset} minutes.", 2)
            return modifiedTimer
        return unmodifiedTimer