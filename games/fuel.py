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

class FuelClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/fuel.py"
        self.prefix = "Fuel:"
        self.url = "https://web.telegram.org/k/#@fueljetton_bot"
        self.pot_full = "Filled"
        self.pot_filling = "to fill"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = True
        self.start_app_xpath = "//span[contains(text(), 'Start pumping oil')]"

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

            self.set_cookies()

        except TimeoutException:
            self.output(f"Bước {self.step} -Không tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.", 1)

        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}", 1)

    def recycle(self):
        try:
            xpath = "//a[text()='Recycling']"
            success = self.move_and_click(xpath, 10, True, "click the 'Recycling' button", self.step, "clickable")
            if success:
                self.output(f"Bước {self.step} -thành công: Đã nhấp vào liên kết 'Tái chế'", 2)
                self.increase_step()
                time.sleep(20)
            else:
                self.output(f"Bước {self.step} -không thành công: Không thể nhấp vào liên kết 'Tái chế'", 2)
                return
                
            xpath = "//button[@class='recycle-button']"
            self.move_and_click(xpath, 10, True, "Refining Oil to Fuel", self.step, "clickable")
            self.increase_step()
                
        except Exception as e:
            self.output(f"An error occurred: {str(e)}")

    def adverts(self):
        xpath = "//a[text()='Upgrades']"
        self.move_and_click(xpath, 10, True, "click the 'Upgrades' button", self.step, "clickable")
        xpath = "//button[contains(., 'Increase multiplier by')]"
        advert = self.move_and_click(xpath, 10, True, "watch an advert", self.step, "clickable")
        if advert:
            self.output(f"Bước {self.step} -Chờ 60 giây để phát quảng cáo.", 3)
            time.sleep(60)
            self.increase_step()
            self.get_balance(True)
            self.get_profit_hour(True)

    def full_claim(self):
        self.step = "100"

        self.launch_iframe()
        self.get_balance(False)
        self.get_profit_hour(False)
        self.quit_driver()
        self.launch_iframe()

        wait_time_text = self.get_wait_time(self.step, "pre-claim") 

        if wait_time_text != "Filled":
            try:
                time_parts = wait_time_text.split()
                hours = int(time_parts[0].strip('h'))
                minutes = int(time_parts[1].strip('m'))
                remaining_wait_time = (hours * 60 + minutes)
                if remaining_wait_time < 5 or self.settings["forceClaim"]:
                    self.settings['forceClaim'] = True
                    self.output(f"Bước {self.step} -thời gian còn lại để yêu cầu ít hơn thời gian bù đắp ngẫu nhiên nên việc áp dụng: settings['forceClaim'] = True", 3)
                else:
                    remaining_wait_time = 30
                    self.adverts()
                    self.output(f"TÌNH TRẠNG: Nồi chưa sẵn sàng để nhận -hãy quay lại sau 30 phút để kiểm tra quảng cáo.", 1)
                    return remaining_wait_time
            except ValueError:
                pass

        if wait_time_text == "không xác định":
            return 15

        try:
            self.output(f"Bước {self.step} -Thời gian chờ yêu cầu trước là: {wait_time_text} và thời gian bù trừ ngẫu nhiên là {self.random_offset} phút.", 1)
            self.increase_step()

            if wait_time_text == "Filled" or self.settings['forceClaim']:
                
                try:
                    xpath = "//button[contains(text(), 'Send to warehouse')]"
                    self.move_and_click(xpath, 10, True, "click the 'Launch' button", self.step, "clickable")

                    self.output(f"Bước {self.step} -Chờ 10 giây để cập nhật tổng số và bộ hẹn giờ...", 3) 
                    time.sleep(10)
                    
                    wait_time_text = self.get_wait_time(self.step, "post-claim") 
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    total_wait_time = self.apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                    self.increase_step()
                    self.get_balance(True)
                    self.get_profit_hour(True)
                    self.increase_step()
                    self.quit_driver()
                    self.launch_iframe()
                    self.increase_step()
                    self.recycle()
                    if wait_time_text == "Filled":
                        self.output(f"Bước {self.step} -Đồng hồ chờ vẫn hiển thị: Đã lấp đầy.", 1)
                        self.output(f"Bước {self.step} -Điều này có nghĩa là xác nhận quyền sở hữu không thành công hoặc có độ trễ >4 phút trong trò chơi.", 1)
                        self.output(f"Bước {self.step} -Chúng tôi sẽ kiểm tra lại sau 1 giờ để xem khiếu nại đã được xử lý chưa và nếu chưa hãy thử lại.", 2)
                    else:
                        self.output(f"TRẠNG THÁI: Nồi đầy sau {total_wait_time} phút. Chúng tôi sẽ quay lại sau 30 phút để kiểm tra quảng cáo.", 1)
                    return 30

                except TimeoutException:
                    self.output(f"TRẠNG THÁI: Quá trình xác nhận quyền sở hữu đã hết thời gian: Có thể trang web bị lag? Sẽ thử lại sau một giờ.", 1)
                    return 60
                except Exception as e:
                    self.output(f"TRẠNG THÁI: Đã xảy ra lỗi khi cố gắng xác nhận quyền sở hữu: {e}\nHãy đợi một giờ và thử lại", 1)
                    return 60

            else:
                matches = re.findall(r'(\d+)([hm])', wait_time_text)
                if matches:
                    total_time = sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)
                    total_time += 1
                    total_time = max(5, total_time) 
                    self.output(f"Bước {self.step} -Chưa đến lúc nhận ví này. Đợi {total_time} phút cho đến khi bộ nhớ đầy.", 2)
                    return total_time 
                else:
                    self.output(f"Bước {self.step} -Không tìm thấy dữ liệu về thời gian chờ? Hãy kiểm tra lại sau một giờ nữa.", 2)
                    return 60 
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi không mong muốn: {e}", 1)
            return 60 
        
    def get_balance(self, claimed=False):
        prefix = "After" if claimed else "Before"
        priority = max(self.settings['verboseLevel'], 2 if claimed else 3)

        xpaths = {
            'fuel': "//span[@class='fuel-balance']",
            'oil': "//span[@class='fuel-balance']/preceding-sibling::span[1]",
        }

        balance = {}

        for resource, xpath in xpaths.items():
            self.move_and_click(xpath, 30, False, f"look for {resource} balance", self.step, "visible")
            balance[resource] = self.monitor_element(xpath)

        balance_text = f"{prefix} BALANCE: {balance['fuel']} fuel & {balance['oil']} oil."
        self.output(f"Step {self.step} - {balance_text}", priority)

        return balance


    def get_profit_hour(self, claimed=False):
        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng lợi nhuận cụ thể XPath
        profit_text = f'{prefix} PROFIT/HOUR:'
        profit_xpath = "//div[div[contains(text(), 'Oil rig')]]//div[last()]"

        try:
            element = None

            xpath = "//a[text()='Upgrades']"
            button = self.move_and_click(xpath, 10, False, "click the 'Upgrades' button", self.step, "clickable")
            if button:
                button.click()

                element = self.strip_html_and_non_numeric(self.monitor_element(profit_xpath))

            #Kiểm tra xem phần tử có phải là Không và xử lý lợi nhuận
            if element:
                self.output(f"Step {self.step} - {profit_text} {element} oil", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Lợi nhuận/Giờ:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký

        self.increase_step()


    def get_wait_time(self, step_number="108", beforeAfter="pre-claim", max_attempts=1):
        for attempt in range(1, max_attempts + 1):
            try:
                self.output(f"Bước {self.step} -kiểm tra xem đồng hồ đã hết chưa...", 3)
                xpath = "//div[@class='in-storage-footer']"
                pot_full_value = self.monitor_element(xpath, 15)
                return pot_full_value
            except Exception as e:
                self.output(f"Bước {self.step} -Đã xảy ra lỗi khi thử {attempt}: {e}", 3)
                return "không xác định"

        return "không xác định"

def main():
    claimer = FuelClaimer()
    claimer.run()

if __name__ == "__main__":
    main()