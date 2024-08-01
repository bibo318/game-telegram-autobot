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

class BlumClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/blum.py"
        self.prefix = "Blum:"
        self.url = "https://web.telegram.org/k/#@BlumCryptoBot"
        self.pot_full = "Filled"
        self.pot_filling = "to fill"
        self.seed_phrase = None
        self.forceLocalProxy = True
        self.forceRequestUserAgent = False
        self.start_app_xpath = "//button[span[contains(text(), 'Ra mắt Blum')]]"

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

            self.set_cookies()

        except TimeoutException:
            self.output(f"Bước {self.step} - Không tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.", 1)

        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}", 1)

    def full_claim(self):
        self.step = "100"

        self.launch_iframe()

        xpath = "//span[contains(text(), 'Phần thưởng hàng ngày của bạn')]"
        present = self.move_and_click(xpath, 20, False, "kiểm tra phần thưởng hàng ngày", self.step, "Dễ thấy")
        self.increase_step()
        reward_text = None
        if present:
            xpath = "(//div[@class='count'])[1]"
            points = self.move_and_click(xpath, 10, False, "get daily points", self.step, "Dễ thấy")
            xpath = "(//div[@class='count'])[2]"
            days = self.move_and_click(xpath, 10, False, "get consecutive days played", self.step, "Dễ thấy")
            reward_text = f"Daily rewards: {points.text} points & {days.text} days."
            xpath = "//button[.//span[text()='Tiếp tục']]"
            self.move_and_click(xpath, 10, True, "nhấp vào tiếp tục", self.step, "Có thể nhấp")
            self.increase_step()

        xpath = "//button[.//div[text()='Tiếp tục']]"
        self.move_and_click(xpath, 10, True, "nhấp vào tiếp tục", self.step, "Có thể nhấp")
        self.increase_step()

        xpath = "//button[.//span[contains(text(), 'Start farming')]][1]"
        self.move_and_click(xpath, 10, True, "nhấp vào nút 'Bắt ​​đầu canh tác' (có thể không có)", self.step, "clickable")
        # self.click_element(xpath)
        self.increase_step()

        self.get_balance(False)

        wait_time_text = self.get_wait_time(self.step, "pre-claim") 

        if wait_time_text != self.pot_full:
            matches = re.findall(r'(\d+)([hm])', wait_time_text)
            remaining_wait_time = (sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)) + self.random_offset
            if remaining_wait_time < 5 or self.settings["forceClaim"]:
                self.settings['forceClaim'] = True
                self.output(f"Bước {self.step} - thời gian còn lại để yêu cầu ít hơn thời gian bù ngẫu nhiên nên áp dụng: cài đặt['forceClaim'] = True", 3)
            else:
                self.output(f"TRẠNG THÁI: Vẫn còn bù {wait_time_text} và {self.random_offset} phút -Đi ngủ thôi. {reward_text}", 1)
                return remaining_wait_time

        if wait_time_text == "Unknown":
            return 15

        try:
            self.output(f"Step {self.step} - Thời gian chờ yêu cầu trước là: {wait_time_text} và thời gian chờ đợi ngẫu nhiên là {self.random_offset} phút.", 1)
            self.increase_step()

            if wait_time_text == self.pot_full or self.settings['forceClaim']:
                try:
                    xpath = "//button[.//div[contains(text(), 'Claim')]]"
                    self.move_and_click(xpath, 10, True, "nhấp vào nút 'Yêu cầu'", self.step, "clickable")
                    # self.click_element(xpath)

                    time.sleep(5)

                    xpath = "//button[.//span[contains(text(), 'Start farming')]][1]"
                    self.move_and_click(xpath, 10, True, "nhấp vào nút 'Bắt ​​đầu canh tác'", self.step, "clickable")
                    # self.click_element(xpath)

                    self.output(f"Bước {self.step} -Chờ 10 giây để cập nhật tổng số và đồng hồ đếm giờ...", 3) 
                    time.sleep(10)
                    
                    wait_time_text = self.get_wait_time(self.step, "post-claim") 
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    total_wait_time = self.apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                    self.increase_step()

                    self.get_balance(True)

                    if wait_time_text == self.pot_full:
                        self.output(f"Step {self.step} - Đồng hồ chờ vẫn hiển thị: Đã đầy.", 1)
                        self.output(f"Step {self.step} - Điều này có nghĩa là xác nhận quyền sở hữu không thành công hoặc trò chơi có độ trễ >4 phút.", 1)
                        self.output(f"Step {self.step} - Chúng tôi sẽ kiểm tra lại sau 1 giờ để xem khiếu nại có được xử lý hay không và nếu không hãy thử lại.", 2)
                    else:
                        self.output(f"TÌNH TRẠNG: Thời gian chờ gửi yêu cầu: {wait_time_text} & Thời gian hẹn giờ mới = {total_wait_time} phút. {reward_text}", 1)
                    return max(60, total_wait_time)

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
                    self.output(f"Step {self.step} - Chưa đến lúc yêu cầu ví này. Đợi {total_time} phút cho đến khi bộ nhớ đầy.", 2)
                    return total_time 
                else:
                    self.output(f"Step {self.step} - Không tìm thấy dữ liệu thời gian chờ? Hãy kiểm tra lại sau một giờ nữa.", 2)
                    return 60
        except Exception as e:
            self.output(f"Step {self.step} - Đã xảy ra lỗi không mong muốn: {e}", 1)
            return 60
        
    def get_balance(self, claimed=False):
        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        priority = max(self.settings['verboseLevel'], default_priority)

        balance_text = f'{prefix} Số Dư:' if claimed else f'{prefix} Số Dư:'
        balance_xpath = f"//div[@class='balance']//div[@class='kit-counter-animation value']"

        try:
            balance_element = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, balance_xpath))
            )

            if balance_element:
                char_elements = balance_element.find_elements(By.XPATH, ".//div[@class='el-char']")
                balance_part = ''.join([char.text for char in char_elements]).strip()
                
                self.output(f"Step {self.step} - {balance_text} {balance_part}", priority)

        except NoSuchElementException:
            self.output(f"Step {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Step {self.step} - Đã xảy ra lỗi: {str(e)}", priority) 

        self.increase_step()

    def get_wait_time(self, step_number="108", beforeAfter="pre-claim", max_attempts=1):
        for attempt in range(1, max_attempts + 1):
            try:
                self.output(f"Step {self.step} - Trước tiên hãy kiểm tra xem thời gian có còn trôi qua không...", 3)
                xpath = "//div[@class='time-left']"
                wait_time_value = self.monitor_element(xpath, 10)
                if wait_time_value != "Unknown":
                    return wait_time_value

                self.output(f"Step {self.step} - Then check if the pot is full...", 3)
                xpath = "//button[.//div[contains(text(), 'Claim')]]"
                pot_full_value = self.monitor_element(xpath, 10)
                if pot_full_value != "Unknown":
                    return self.pot_full
                return "Unknown"
            except Exception as e:
                self.output(f"Step {self.step} - Đã xảy ra lỗi khi thử {attempt}: {e}", 3)
                return "Unknown"

        return "Unknown"

def main():
    claimer = BlumClaimer()
    claimer.run()

if __name__ == "__main__":
    main()