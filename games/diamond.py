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
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException, ElementClickInterceptedException
from datetime import datetime, timedelta
from selenium.webdriver.chrome.service import Service as ChromeService

from claimer import Claimer

class DiamondClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/diamond.py"
        self.prefix = "Diamond:"
        self.url = "https://web.telegram.org/k/#@holdwallet_bot"
        self.pot_full = "Filled"
        self.pot_filling = "to fill"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False
        self.start_app_xpath = "//div[text()='Open Wallet']"

    def __init__(self):
        self.settings_file = "variables.txt"
        self.status_file_path = "status.txt"
        self.wallet_id = ""
        self.load_settings()
        self.random_offset = random.randint(self.settings['lowestClaimOffset'], self.settings['highestClaimOffset'])
        super().__init__()

    def next_steps(self):
        if self.step:
            pass
        else:
            self.step = "01"

        try:
            self.launch_iframe()
            self.increase_step()

            # Attempt to interact with elements within the iframe.
            # Let's click the login button first:
            xpath = "//a[contains(text(), 'Login')]"
            self.target_element = self.move_and_click(xpath, 30, False, "find the HoldWallet log-in button", "08", "visible")
            self.driver.execute_script("arguments[0].click();", self.target_element)
            self.increase_step()

            # Then look for the seed phase textarea:
            xpath = "//div[@class='form-input'][label[text()='Seed or private key']]/textarea"
            input_field = self.move_and_click(xpath, 30, True, "locate seedphrase textbox", self.step, "clickable")
            if not self.imported_seedphrase:
                self.imported_seedphrase = self.validate_seed_phrase()
            input_field.send_keys(self.imported_seedphrase) 
            self.output(f"Bước {self.step} -Đã nhập thành công cụm từ hạt giống...",3)
            self.increase_step()

            # Click the continue button after seed phrase entry:
            xpath = "//button[contains(text(), 'Continue')]"
            self.move_and_click(xpath, 30, True, "nhấp vào tiếp tục sau khi nhập seedphrase", self.step, "clickable")
            self.increase_step()

            # Click the account selection button:
            xpath = "//div[contains(text(), 'Select account')]"
            self.move_and_click(xpath, 20, True, "nhấp vào lựa chọn tài khoản (có thể không có)", self.step, "clickable")
            self.increase_step()

            if not (self.forceRequestUserAgent or self.settings["requestUserAgent"]):
                cookies_path = f"{self.session_path}/cookies.json"
                cookies = self.driver.get_cookies()
                with open(cookies_path, 'w') as file:
                    json.dump(cookies, file)
            else:
                user_agent = self.prompt_user_agent()
                cookies_path = f"{self.session_path}/cookies.json"
                cookies = self.driver.get_cookies()
                cookies.append({"name": "user_agent", "value": user_agent})  # Save user agent to cookies
                with open(cookies_path, 'w') as file:
                    json.dump(cookies, file)

        except TimeoutException:
            self.output(f"Bước {self.step} -Không tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.",1)

        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}",1)

    def full_claim(self):
        self.step = "100"

        self.launch_iframe()

        # Best on Standalone:
        xpath = "//p[text()='Storage']"
        self.move_and_click(xpath, 15, True, "nhấp vào liên kết 'storage'", self.step, "clickable")
        self.increase_step

        # Best on Docker!:
        xpath = "//h2[text()='Mining']"
        self.move_and_click(xpath, 15, True, "nhấp vào liên kết 'storage' thay thế (có thể không có)", self.step, "clickable")
        self.increase_step

        self.get_balance(False)
        self.get_profit_hour(False)

        wait_time_text = self.get_wait_time(self.step, "pre-claim") 

        if wait_time_text != "0h 0m to fill":
            matches = re.findall(r'(\d+)([hm])', wait_time_text)
            remaining_wait_time = (sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)) + self.random_offset
            if remaining_wait_time < 5 or self.settings["forceClaim"]:
                self.settings['forceClaim'] = True
                self.output(f"Bước {self.step} -thời gian còn lại để yêu cầu ít hơn thời gian bù đắp ngẫu nhiên nên việc áp dụng: settings['forceClaim'] = True", 3)
            else:
                self.output(f"TÌNH TRẠNG: Xem xét {wait_time_text}, chúng tôi sẽ quay lại ngủ trong {remaining_wait_time} phút.", 1)
                return remaining_wait_time

        if wait_time_text == "không xác định":
            return 15

        try:
            self.output(f"Bước {self.step} -Thời gian chờ yêu cầu trước là: {wait_time_text} và thời gian bù trừ ngẫu nhiên là {self.random_offset} phút.",1)
            self.increase_step()

            if wait_time_text == "0h 0m to fill" or self.settings['forceClaim']:
                try:

                    # Let's see if we have news to read
                    try:
                        original_window = self.driver.current_window_handle
                        xpath = "//button[contains(text(), 'Check NEWS')]"
                        success = self.move_and_click(xpath, 10, True, "kiểm tra TIN TỨC.", self.step, "clickable")
                        if success:
                            self.output(f"Bước {self.step} -cố gắng chuyển về iFrame.")
                            self.driver.switch_to.window(original_window)
                    except TimeoutException:
                        if self.settings['debugIsOn']:
                            self.output(f"Bước {self.step} -Không có tin tức nào để kiểm tra hoặc không tìm thấy nút.", 3)
                    self.increase_step()


                    # Click on the "Claim" button:
                    xpath = "//button[contains(text(), 'Claim')]"
                    self.move_and_click(xpath, 30, True, "nhấp vào nút claim", self.step, "clickable")
                    self.increase_step()

                    # Now let's try again to get the time remaining until filled. 
                    # 4th April 24 - Let's wait for the spinner to disappear before trying to get the new time to fill.
                    self.output(f"Bước {self.step} -Đợi Claim spinner đang chờ xử lý ...",2)
                    time.sleep(5)
                    wait_time_text = self.get_wait_time(self.step, "post-claim") 
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    total_wait_time = self.apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                    self.increase_step()

                    self.get_balance(True)
                    self.get_profit_hour(True)

                    if wait_time_text == "0h 0m to fill":
                        self.output(f"TRẠNG THÁI: Đồng hồ chờ vẫn hiển thị: Đã đầy",1)
                        self.output(f"Bước {self.step} -Điều này có nghĩa là xác nhận quyền sở hữu không thành công hoặc có độ trễ >4 phút trong trò chơi.",1)
                        self.output(f"Bước {self.step} -Chúng tôi sẽ kiểm tra lại sau 1 giờ để xem khiếu nại đã được xử lý chưa và nếu chưa hãy thử lại.",2)
                    else:
                        self.output(f"TRẠNG THÁI: Xác nhận quyền sở hữu thành công: Yêu cầu tiếp theo {wait_time_text} /{total_wait_time} phút.",1)
                    return max(60, total_wait_time)

                except TimeoutException:
                    self.output(f"TRẠNG THÁI: Quá trình xác nhận quyền sở hữu đã hết thời gian: Có thể trang web bị lag? Sẽ thử lại sau một giờ.",1)
                    return 60
                except Exception as e:
                    self.output(f"TRẠNG THÁI: Đã xảy ra lỗi khi cố gắng xác nhận quyền sở hữu: {e}\nHãy đợi một giờ và thử lại",1)
                    return 60

            else:
                # If the wallet isn't ready to be claimed, calculate wait time based on the timer provided on the page
                matches = re.findall(r'(\d+)([hm])', wait_time_text)
                if matches:
                    total_time = sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)
                    total_time += 1
                    total_time = max(5, total_time) # Wait at least 5 minutes or the time
                    self.output(f"Bước {self.step} -Chưa đến lúc nhận ví này. Đợi {total_time} phút cho đến khi bộ nhớ đầy.",2)
                    return total_time 
                else:
                    self.output(f"Bước {self.step} -Không tìm thấy dữ liệu về thời gian chờ? Hãy kiểm tra lại sau một giờ nữa.",2)
                    return 60  # Default wait time when no specific time until filled is found.
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi không mong muốn: {e}",1)
            return 60  # Default wait time in case of an unexpected error
        
    def get_balance(self, claimed=False):

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        # Dynamically adjust the log priority
        priority = max(self.settings['verboseLevel'], default_priority)

        # Construct the specific balance XPath
        balance_text = f'{prefix} BALANCE:' if claimed else f'{prefix} BALANCE:'
        balance_xpath = f"//small[text()='DMH Balance']/following-sibling::div"

        try:
            element = self.strip_html_and_non_numeric(self.monitor_element(balance_xpath))

            # Check if element is not None and process the balance
            if element:
                self.output(f"Step {self.step} - {balance_text} {element}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  # Provide error as string for logging

        # Increment step function, assumed to handle next step logic
        self.increase_step()

    def get_profit_hour(self, claimed=False):

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        # Dynamically adjust the log priority
        priority = max(self.settings['verboseLevel'], default_priority)

        # Construct the specific profit XPath
        profit_text = f'{prefix} PROFIT/HOUR:'
        profit_xpath = "//div[div[p[text()='Storage']]]//span[last()]"

        try:
            element = self.strip_non_numeric(self.monitor_element(profit_xpath))

            # Check if element is not None and process the profit
            if element:
                self.output(f"Step {self.step} - {profit_text} {element}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Lợi nhuận/Giờ:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  # Provide error as string for logging

        # Increment step function, assumed to handle next step logic
        self.increase_step()

    def get_wait_time(self, step_number="108", beforeAfter="pre-claim"):
        try:
            xpath = "//div[div[p[text()='Storage']]]//span[contains(text(), 'to fill') or contains(text(), 'Filled')]"
            wait_time_element = self.move_and_click(xpath, 20, True, f"get the {beforeAfter} wait timer", step_number, "visible")
            # Check if wait_time_element is not None
            if wait_time_element is not None:
                return wait_time_element.text
            else:
                return "không xác định"
        except Exception as e:
            self.output(f"Step {step_number} - Đã xảy ra lỗi: {e}", 3)
            return "không xác định"

def main():
    claimer = DiamondClaimer()
    claimer.run()

if __name__ == "__main__":
    main()