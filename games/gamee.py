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

class GameeClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/gamee.py"
        self.prefix = "Gamee:"
        self.url = "https://web.telegram.org/k/#@gamee"
        self.pot_full = "Filled"
        self.pot_filling = "Mining"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False
        self.start_app_xpath = "//div[text()='Open app']"

    def __init__(self):
        self.settings_file = "variables.txt"
        self.status_file_path = "status.txt"
        self.wallet_id = ""
        self.load_settings()
        self.random_offset = random.randint(self.settings['lowestClaimOffset'], self.settings['highestClaimOffset'])
        super().__init__()

    def launch_iframe(self):
        super().launch_iframe()

        #self.driver.switch_to.default_content()
#iframe = self.driver.find_element(By.TAG_NAME, "iframe")
#iframe_url = iframe.get_attribute("src")
#iframe_url = iframe_url.replace("tgWebAppPlatform=web", "tgWebAppPlatform=android")
#self.driver.execute_script("arguments[0].src = đối số[1];", iframe, iframe_url)
#self.driver.execute_script("arguments[0].contentWindow.location.reload();", iframe)
#WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, f"//iframe[@src='{iframe_url}']")))
#self.driver.switch_to.default_content()
#self.driver.switch_to.frame(iframe)
#Mở tab trong cửa sổ chính
        self.driver.switch_to.default_content()
        self.driver.execute_script("location.href = document.querySelector('iframe').src")

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

        self.get_balance(False)
        self.get_profit_hour(False)

        clicked_it = False

        status_text = ""

        ## BẮT ĐẦU KHAI THÁC -clear_overlays kích thích di chuyển phần tử lên đầu trang và chồng lên các mục khác
        try:

            xpath = "//div[contains(@class, 'eWLHYP')]" #Nút BẮT ĐẦU KHAI THÁC
            button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            if button:
                button.click()
                self.output(f"Bước {self.step} -Đã nhấp thành công vào nút 'Khai thác'.", 3)
                status_text = "TÌNH TRẠNG: Bắt đầu KHAI THÁC"

        except TimeoutException:
            try:

                xpath = "//div[contains(@class, 'cYeqKR')]" #Nút KHAI THÁC
                button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                self.output(f"Bước {self.step} -Hiện đang khai thác: {'YES' if button else 'NO'}.", 3)
                status_text = "TÌNH TRẠNG: Hiện đang khai thác" if button else "TÌNH TRẠNG: Không khai thác"

            except TimeoutException:
                self.output(f"Bước {self.step} -KHÔNG tìm thấy nút KHAI THÁC .\n",3)
                status_text = "TRẠNG THÁI: KHÔNG tìm thấy nút KHAI THÁC"

        self.increase_step()

        #BẮT ĐẦU KHAI THÁC
#xpath = "//div[chứa(@class, 'eWLHYP')]"
#xpath = "//div[contains(@class, 'cYeqKR')]"
#nút = self.move_and_click(xpath, 8, Sai, "nhấp vào 'Quay TAB'", self.step, "có thể nhấp")
#nút nếu: nút.click()
#self.increase_step()

        xpath = "//div[contains(@class, 'wxeDq') and .//text()[contains(., 'Spin')]]"
        button = self.move_and_click(xpath, 8, False, "click the 'Spin TAB'", self.step, "clickable")
        if button: button.click()
        self.increase_step()

        #Đợi nút 'VÒNG QUAY MIỄN PHÍ' xuất hiện
        xpath = "//button[.//text()[contains(., 'available')]]"

        while True:

            try:
                button = self.move_and_click(xpath, 30, False, "click the 'FREE Spin'", self.step, "clickable")
                if not button: break
                if button: button.click()
            except TimeoutException:
                break

        self.get_balance(True)
        self.get_profit_hour(True)
        
        wait_time = self.get_wait_time(self.step, "pre-claim") 

        if wait_time is None:
            self.output(f"{status_text} - Không thể có được thời gian chờ đợi. Lần thử tiếp theo sau 60 phút", 3)
            return 60
        else:
            self.output(f"{status_text} - Tiếp theo thử vào {self.show_time(wait_time)}.", 2)
            return wait_time

    def get_balance(self, claimed=False):

        xpath = "//div[contains(@class, 'wxeDq') and .//text()[contains(., 'Mine')]]"
        button = self.move_and_click(xpath, 8, False, "click the 'Mine TAB'", self.step, "clickable")
        if button: button.click()
        self.increase_step()

        self.driver.execute_script("location.href = 'https://prizes.gamee.com/telegram/mining/12'")

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        #Tự động điều chỉnh mức độ ưu tiên của nhật ký
        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng số dư cụ thể XPath
        balance_text = f'{prefix} Số Dư:' if claimed else f'{prefix} Số Dư:'
        balance_xpath = "//h2[@id='animated-mining-balance-id']"

        try:
            element = self.monitor_element(balance_xpath)

            #Kiểm tra xem phần tử có phải là Không và xử lý số dư
            if element:
                cleaned_balance = self.strip_html_and_non_numeric(element)
                self.output(f"Bước {self.step} - {balance_text} {cleaned_balance}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
#Hàm bước tăng dần, giả sử để xử lý logic bước tiếp theo
        self.increase_step()

    def get_profit_hour(self, claimed=False):

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        #Tự động điều chỉnh mức độ ưu tiên của nhật ký
        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng lợi nhuận cụ thể XPath
        profit_text = f'{prefix} PROFIT/HOUR:'
        profit_xpath = "(//p[contains(@class, 'jQUosL')])[1]"

        try:
            element = self.monitor_element(profit_xpath)
            if element:
                profit_part = self.strip_html_and_non_numeric(element)
                self.output(f"Bước {self.step} - {profit_text} {profit_part}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Lợi nhuận/Giờ:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
#Hàm bước tăng dần, giả sử để xử lý logic bước tiếp theo
        self.increase_step()

    def get_wait_time(self, step_number="108", beforeAfter="pre-claim"):
        try:

            self.output(f"Bước {self.step} -kiểm tra xem đồng hồ đã hết chưa...", 3)

            xpath = "(//p[contains(@class, 'bEEYcp')])[1]"
            actual = float(self.monitor_element(xpath, 15))

            xpath = "(//p[contains(@class, 'bEEYcp')])[2]"
            max = float(self.monitor_element(xpath, 15))

            xpath = "(//p[contains(@class, 'jQUosL')])[1]"
            production = float(self.monitor_element(xpath, 15))

            wait_time = int(((max-actual)/production)*60)

            return wait_time          

        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}", 3)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}_get_wait_time_error.png"
                self.driver.save_screenshot(screenshot_path)
                self.output(f"Ảnh chụp màn hình đã được lưu vào {screenshot_path}", 3)

            return None

def main():
    claimer = GameeClaimer()
    claimer.run()

if __name__ == "__main__":
    main()
