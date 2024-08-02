
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

class LumCityClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/lumcity.py"
        self.prefix = "LumCity:"
        self.url = "https://web.telegram.org/k/#@LumCity_bot"
        self.pot_full = "Filled"
        self.pot_filling = "to fill"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False
        self.start_app_xpath = "//span[contains(text(), 'Open the App')]"

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

    def full_claim(self):
        self.step = "100"

        self.launch_iframe()
        self.output(f"Step {self.step} - Short wait to let the totals load", 3)
        time.sleep(10)

        self.get_balance(False)

        xpath = "//button[contains(normalize-space(.), 'Claim')]"
        self.move_and_click(xpath, 20, True, "move to the 'Claim' screen", self.step, "clickable")

        remaining_wait_time = self.get_wait_time(self.step, "pre-claim")

        try:
            remaining_wait_time = int(remaining_wait_time)
        except ValueError:
            self.output("STATUS: Wait time is không xác định due to non-numeric input.", 1)
            return 60

        if remaining_wait_time > 0:
            if remaining_wait_time < 5 or self.settings["forceClaim"]:
                self.settings['forceClaim'] = True
                self.output(f"Bước {self.step} -thời gian còn lại để yêu cầu ít hơn thời gian bù đắp ngẫu nhiên nên việc áp dụng: settings['forceClaim'] = True", 3)
            else:
                self.output(f"STATUS: Wait time is {remaining_wait_time} minutes and off-set of {self.random_offset}.", 1)
                return remaining_wait_time + self.random_offset


        try:
            if remaining_wait_time < 5 or self.settings['forceClaim']:
                try:
                    xpath = "//button[contains(normalize-space(.), 'Claim')]"
                    self.move_and_click(xpath, 20, True, "nhấp vào nút 'Claim", self.step, "clickable")
                    self.increase_step()

                    xpath = "//div[contains(@class, '_msgWrapper_7jeg3_57')]//span[1]"
                    reward_value = self.monitor_element(xpath, 20)
                    if reward_value:
                        self.output(f"Step {self.step} - This claim increased the balance: +{reward_value}", 1)

                    xpath = "//div[contains(@class, '_btnContainer')]//button[text()='Ok']"
                    self.move_and_click(xpath, 20, True, "click the 'OK' button", self.step, "clickable")
                    self.increase_step()
                    
                    remaining_wait_time = self.get_wait_time(self.step, "post-claim")
                    self.increase_step()

                    self.launch_iframe()
                    self.output(f"Step {self.step} - Short wait to let the totals load", 3)
                    time.sleep(10)

                    self.get_balance(True)

                    if remaining_wait_time == 0:
                        self.output(f"Bước {self.step} -Đồng hồ chờ vẫn hiển thị: Đã lấp đầy.", 1)
                        self.output(f"Step {self.step} - This means either the claim failed, or there is lag in the game.", 1)
                        self.output(f"Bước {self.step} -Chúng tôi sẽ kiểm tra lại sau 1 giờ để xem khiếu nại đã được xử lý chưa và nếu chưa hãy thử lại.", 2)
                        return 60
                    else:
                        total_time = self.apply_random_offset(remaining_wait_time)
                        self.output(f"STATUS: Pot full in {remaining_wait_time} minutes, plus an off-set of {self.random_offset}.", 1)
                    return total_time

                except TimeoutException:
                    self.output(f"TRẠNG THÁI: Quá trình xác nhận quyền sở hữu đã hết thời gian: Có thể trang web bị lag? Sẽ thử lại sau một giờ.", 1)
                    return 60
                except Exception as e:
                    self.output(f"TRẠNG THÁI: Đã xảy ra lỗi khi cố gắng xác nhận quyền sở hữu: {e}\nHãy đợi một giờ và thử lại", 1)
                    return 60
            else:
                if remaining_wait_time:
                    total_time = self.apply_random_offset(remaining_wait_time)
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
        default_priority = 2 if claimed else 3

        priority = max(self.settings['verboseLevel'], default_priority)

        balance_text = f'{prefix} Golt BALANCE:' if claimed else f'{prefix} BALANCE:'
        balance_xpath = f"(//div[contains(@class, '1615f_24')])[2]"
        balance_part = None

        try:
            self.move_and_click(balance_xpath, 30, False, "look for Golt balance", self.step, "visible")
            balance_part = self.strip_html_tags(self.monitor_element(balance_xpath))
            self.output(f"Step {self.step} - {balance_text} {balance_part}", priority)
        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)

        self.increase_step()
        return balance_part  #Đã thêm câu lệnh trả về để đảm bảo số dư_part được trả về

    def strip_html_tags(self, text):
        clean = re.compile('<.*?>')
        text_without_html = re.sub(clean, '', text)
        text_cleaned = re.sub(r'[^0-9:.]', '', text_without_html)
        return text_cleaned

    def extract_single_number(self, text):
        numbers = re.findall(r'[\d.]+', text)
        if numbers:
            return numbers[0]
        return None

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

    def get_wait_time(self, step_number="108", beforeAfter="pre-claim", max_attempts=1):
        for attempt in range(1, max_attempts + 1):
            try:
                self.output(f"Bước {self.step} -kiểm tra xem đồng hồ đã hết chưa...", 3)
                xpath = "//span[text()='Fill Time']/ancestor::div[1]/following-sibling::div"
                pot_full_value = self.extract_time(self.strip_html_tags(self.monitor_element(xpath, 15)))
                return pot_full_value
            except Exception as e:
                self.output(f"Bước {self.step} -Đã xảy ra lỗi khi thử {attempt}: {e}", 3)
                return "không xác định"
        return "không xác định"

def main():
    claimer = LumCityClaimer()
    claimer.run()

if __name__ == "__main__":
    main()