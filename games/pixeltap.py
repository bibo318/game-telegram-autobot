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

class PixelTapClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/pixeltap.py"
        self.prefix = "PixelTap:"
        self.url = "https://web.telegram.org/k/#@pixelversexyzbot"
        self.pot_full = "Filled"
        self.pot_filling = "Mining"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False
        self.start_app_xpath = "//div[contains(@class, 'new-message-wrapper')]//div[contains(text(), 'Fight for supply')]"

    def __init__(self):
        self.settings_file = "variables.txt"
        self.status_file_path = "status.txt"
        self.wallet_id = ""
        self.load_settings()
        self.random_offset = random.randint(self.settings['lowestClaimOffset'], self.settings['highestClaimOffset'])
        super().__init__()

    def launch_iframe(self):
        super().launch_iframe()

        #Mở tab trong cửa sổ chính
        self.driver.switch_to.default_content()

        iframe = self.driver.find_element(By.TAG_NAME, "iframe")
        iframe_url = iframe.get_attribute("src")
        iframe_url = iframe_url.replace("tgWebAppPlatform=web", "tgWebAppPlatform=android")

        self.driver.execute_script("location.href = '" + iframe_url + "'")

    def next_steps(self):
        if self.step:
            pass
        else:
            self.step = "01"

        try:
            self.launch_iframe()
            self.increase_step()

            self.set_cookies()

        except TimeoutException:
            self.output(f"Bước {self.step} -Không tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.",1)

        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}",1)

    def full_claim(self):
        self.step = "100"
        self.launch_iframe()

        #Vô hiệu hóa phương thức
        xpath = "(//div[contains(@class, 'MuiBackdrop-root')])[last()]"
        button = self.move_and_click(xpath, 8, False, "disable modals #1 (may not be present)", self.step, "clickable")
        if button: button.click()

        xpath = "(//div[contains(@class, 'MuiBackdrop-root')])[last()]"
        button = self.move_and_click(xpath, 8, False, "disable modals #2 (may not be present)", self.step, "clickable")
        if button: button.click()
            
        self.increase_step()

        status_text = None

        #Khẳng định
        xpath = "//button[contains(@class, 'claimButton')]"
        button = self.move_and_click(xpath, 8, False, "nhấp vào nút 'Claim", self.step, "clickable")
        if button:button.click()
        self.increase_step()

        #Chọn tab 'Phần thưởng'
        xpath = "//a[contains(span/text(), 'Rewards')]"
        button = self.move_and_click(xpath, 8, False, "click the 'Rewards TAB'", self.step, "clickable")
        if button:
            button.click()
            status_text = "Reward claimed. "
        self.increase_step()

        #Chọn tab 'Phần thưởng'
        xpath = "//button//span[contains(text(), 'Claim')]"
        button = self.move_and_click(xpath, 8, False, "open the 'CLAIM' pop-up", self.step, "clickable")
        if button:
            button.click()

            xpath = "//div[contains(text(), 'Claim') and not(contains(@class, 'disabled'))]"
            button = self.move_and_click(xpath, 8, False, "nhấp vào nút 'Claim", self.step, "clickable")
            if button: button.click()

            xpath = "//button[@class='closeBtn']"
            button = self.move_and_click(xpath, 8, False, "exit the 'CLAIM' pop-up", self.step, "clickable")
            if button: 
                button.click()
                status_text += "Claim made."

        if not status_text:
            status_text = "No reward or claim made on this occassion."

        self.output(f"STATUS: {status_text}",1)

        self.increase_step()

        self.get_balance(False)

        wait_time = self.get_wait_time(self.step, "pre-claim") 

        try:
            wait_time = int(wait_time)
            if wait_time < 60:
                wait_time = 60
        except (ValueError, TypeError):
             wait_time = 60
        #Bây giờ bạn có thể gọi Random.randint một cách an toàn
        random_value = random.randint(60, wait_time)


    def get_balance(self, claimed=False):

        xpath = "//a[contains(span/text(), 'Earn')]"
        button = self.move_and_click(xpath, 8, False, "click the 'Earn TAB'", self.step, "clickable")
        if button: button.click()
        self.increase_step()

        def strip_html_and_non_numeric(text):
            """Remove HTML tags and keep only numeric characters and decimal points."""
            #Xóa thẻ HTML
            clean = re.compile('<.*?>')
            text_without_html = clean.sub('', text)
            #Chỉ giữ lại các ký tự số và dấu thập phân
#num_text = re.sub(r'[^0-9.]', '', text_without_html)
            return text_without_html

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        #Tự động điều chỉnh mức độ ưu tiên của nhật ký
        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng số dư cụ thể XPath
        balance_text = f'{prefix} BALANCE:' if claimed else f'{prefix} BALANCE:'
        balance_xpath = "//div[@class='_balance_11ewj_19']" 

        try:
            element = self.monitor_element(balance_xpath)

            #Kiểm tra xem phần tử có phải là Không và xử lý số dư
            if element:
                cleaned_balance = strip_html_and_non_numeric(element)
                self.output(f"Step {self.step} - {balance_text} {cleaned_balance}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
#Hàm bước tăng dần, giả sử để xử lý logic bước tiếp theo
        self.increase_step()


    def get_wait_time(self, step_number="108", beforeAfter="pre-claim"):
        try:
            self.output(f"Bước {self.step} -kiểm tra xem đồng hồ đã hết chưa...", 3)
        
            xpath = "//div[contains(@class, 'claimTimer')]"
            wait_time_str = self.extract_time(self.strip_html_tags(self.monitor_element(xpath, 15)))

            if wait_time_str == "không xác định":
                wait_time = 60
            else:
                wait_time = int(wait_time_str)

            self.output(f"Step {self.step} - The wait time is {wait_time} minutes.")

            return wait_time          
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}", 3)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}_get_wait_time_error.png"
                self.driver.save_screenshot(screenshot_path)
                self.output(f"Ảnh chụp màn hình đã được lưu vào {screenshot_path}", 3)
            return 60


    def extract_time(self, text):
        time_parts = text.split(':')
        if len(time_parts) == 3:
            try:
                hours = int(time_parts[0].strip())
                minutes = int(time_parts[1].strip())
                return hours * 60 + minutes
            except ValueError:
                return "không xác định"
        return "không xác định"
    
    def strip_html_tags(self, text):
        clean = re.compile('<.*?>')
        text_without_html = re.sub(clean, '', text)
        text_cleaned = re.sub(r'[^0-9:.]', '', text_without_html)
        return text_cleaned

def main():
    claimer = PixelTapClaimer()
    claimer.run()

if __name__ == "__main__":
    main()