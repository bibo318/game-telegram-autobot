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

from claimer import Claimer

class TimeFarmClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/time-farm.py"
        self.prefix = "Time-Farm:"
        self.url = "https://web.telegram.org/k/#@TimeFarmCryptoBot"
        self.pot_full = "Filled"
        self.pot_filling = "to fill"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False
        self.start_app_xpath = "//span[contains(text(), 'Open App')]"

    def __init__(self):
        self.settings_file = "variables.txt"
        self.status_file_path = "status.txt"
        self.wallet_id = ""
        self.load_settings()
        self.random_offset = random.randint(max(self.settings['lowestClaimOffset'], 0), max(self.settings['highestClaimOffset'], 0))
        super().__init__()

    def next_steps(self):

        if self.step:
            pass
        else:
            self.step = "01"

        try:
            self.launch_iframe()
            self.increase_step()

            cookies_path = f"{self.session_path}/cookies.json"
            cookies = self.driver.get_cookies()
            with open(cookies_path, 'w') as file:
                json.dump(cookies, file)

        except TimeoutException:
            self.output(f"Bước {self.step} -Không tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.",1)

        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}",1)

    def full_claim(self):

        self.step = "100"

        self.launch_iframe()

        xpath = "//div[@class='app-container']//div[@class='btn-text' and contains(., 'Claim')]"
        start_present = self.move_and_click(xpath, 8, False, "make 'Claim' (may not be present)", self.step, "clickable")

        self.get_balance(False)
        self.increase_step()

        xpath = "//div[@class='farming-button-block'][.//span[text()='Start']]"
        start_present = self.move_and_click(xpath, 8, False, "click the 'Start' button (may not be present)", self.step, "clickable")
        if start_present:
            self.click_element(xpath, 20)
        self.increase_step()

        remaining_time = self.get_wait_time()
        self.increase_step()
        
        if isinstance(remaining_time, (int, float)):
            remaining_time = self.apply_random_offset(remaining_time)
            self.output(f"STATUS: We still have {remaining_time} minutes left to wait - sleeping.", 1)
            return remaining_time

        xpath = "//div[@class='farming-button-block'][.//span[text()='Claim']]"
        self.move_and_click(xpath, 20, False, "look for the claim button.", self.step, "visible")
        success = self.click_element(xpath, 20)
        if success:
            self.increase_step()
            self.output(f"STATUS: We appear to have correctly clicked the claim button.",1)
            xpath = "//div[@class='farming-button-block'][.//span[text()='Start']]"
            start_present = self.move_and_click(xpath, 20, False, "click the 'Start' button", self.step, "clickable")
            if start_present:
                self.click_element(xpath, 20)
                self.increase_step()
            remaining_time = self.get_wait_time()
            self.increase_step()
            self.get_balance(True)
            return self.apply_random_offset(remaining_time)
        else:
            self.output(f"STATUS: The claim button wasn't clickable on this occassion.",1)
            return 60
            
    def get_balance(self, claimed=False):

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        #Tự động điều chỉnh mức độ ưu tiên của nhật ký
        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng số dư cụ thể XPath
        balance_text = f'{prefix} BALANCE:' if claimed else f'{prefix} BALANCE:'
        balance_xpath = f"//div[@class='balance']"
        try:
            balance_part = self.monitor_element(balance_xpath)
            #Loại bỏ mọi thẻ HTML và ký tự không mong muốn
            balance_part = "$" + self.strip_html_tags(balance_part)
            #Kiểm tra xem phần tử có phải là Không và xử lý số dư
            self.output(f"Step {self.step} - {balance_text} {balance_part}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký

    def strip_html_tags(self, text):
        """Remove HTML tags, newlines, and excess spaces from a given string."""
        clean = re.compile('<.*?>')
        text_without_html = re.sub(clean, '', text)
        #Xóa mọi ký tự không phải số và không phải dấu hai chấm, nhưng tạm thời giữ khoảng trắng
        text_cleaned = re.sub(r'[^0-9: ]', '', text_without_html)
        #Xóa dấu cách
        text_cleaned = re.sub(r'\s+', '', text_cleaned)
        return text_cleaned

    def extract_time(self, text):
        """Extract time from the cleaned text and convert to minutes."""
        time_parts = text.split(':')
        if len(time_parts) == 3:
            try:
                hours = int(time_parts[0].strip())
                minutes = int(time_parts[1].strip())
                #Chúng tôi cho rằng không cần giây để tính phút
#giây = int(time_parts[2].strip())
                return hours * 60 + minutes
            except ValueError:
                return "không xác định"
        return "không xác định"

    def get_wait_time(self, step_number="108", beforeAfter="pre-claim", max_attempts=1):

        for attempt in range(1, max_attempts + 1):
            try:
                self.output(f"Bước {self.step} -kiểm tra xem đồng hồ đã hết chưa...", 3)
                xpath = "//table[@class='scroller-table']"
                pot_full_value = self.monitor_element(xpath, 15)
                
                #Loại bỏ mọi thẻ HTML và ký tự không mong muốn
                pot_full_value = self.strip_html_tags(pot_full_value)
                
                #Chuyển đổi thành phút
                wait_time_in_minutes = self.extract_time(pot_full_value)
                return wait_time_in_minutes
            except Exception as e:
                self.output(f"Bước {self.step} -Đã xảy ra lỗi khi thử {attempt}: {e}", 3)
                return "không xác định"

        #Nếu mọi nỗ lực đều thất bại
        return "không xác định"

def main():
    claimer = TimeFarmClaimer()
    claimer.run()

if __name__ == "__main__":
    main()