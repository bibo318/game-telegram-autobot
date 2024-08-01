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

class WaveClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/wave.py"
        self.prefix = "Wave:"
        self.url = "https://web.telegram.org/k/#@waveonsuibot"
        self.pot_full = "Filled"
        self.pot_filling = "to fill"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False
        self.start_app_xpath = "//a[@href='https://t.me/waveonsuibot/walletapp']"

    def __init__(self):
        self.settings_file = "variables.txt"
        self.status_file_path = "status.txt"
        self.wallet_id = ""
        self.load_settings()
        self.random_offset = random.randint(self.settings['lowestClaimOffset'], self.settings['highestClaimOffset']) + 1
        super().__init__()

    def next_steps(self):
        if self.step:
            pass
        else:
            self.step = "01"

        try:
            self.launch_iframe()
            self.increase_step()

            try:
                xpath = "//button[contains(text(), 'Login')]"
                login_button = WebDriverWait(self.driver, 30).until(
                    EC.visibility_of_element_located((By.XPATH, xpath))
                )
        
                self.driver.execute_script("arguments[0].click();", login_button)
                self.output(f"Bước {self.step} -Đã nhấp vào nút đăng nhập thành công...", 2)
                self.increase_step()

            except Exception as e:
                self.output(f"Bước {self.step} -Nhập không thành công seed: {str(e)}", 2)

            try:
                xpath = "//p[contains(text(), 'Seed cụm từ hoặc Khóa riêng')]/following-sibling::textarea[1]"
                input_field = WebDriverWait(self.driver, 30).until(
                    EC.visibility_of_element_located((By.XPATH, xpath))
                )
        
                self.driver.execute_script("arguments[0].click();", input_field)
                input_field.send_keys(self.validate_seed_phrase())
                self.output(f"Bước {self.step} -Đã có thể nhập thành công seed...", 3)
                self.increase_step()

            except Exception as e:
                self.output(f"Step {self.step} - Không thể nhập cụm từ seed: {str(e)}", 2)

            xpath = "//button[contains(text(), 'Tiếp tục')]"
            self.move_and_click(xpath, 30, True, "nhấp vào tiếp tục sau khi nhập cụm từ seed", self.step, "clickable")
            self.increase_step()

            xpath = "//button[.//span[contains(text(), 'Xác nhận ngay')]]"
            self.move_and_click(xpath, 30, True, "nhấp vào liên kết 'Xác nhận ngay'", self.step, "clickable")

            self.set_cookies()

        except TimeoutException:
            self.output(f"Step {self.step} - Không thể tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.", 1)

        except Exception as e:
            self.output(f"Step {self.step} - Đã xảy ra lỗi: {e}", 1)

    def full_claim(self):
        self.step = "100"

        def apply_random_offset(unmodifiedTimer):
            lowest_claim_offset = max(0, self.settings['lowestClaimOffset'])
            highest_claim_offset = max(0, self.settings['highestClaimOffset'])
            if self.settings['lowestClaimOffset'] <= self.settings['highestClaimOffset']:
                self.random_offset = random.randint(lowest_claim_offset, highest_claim_offset) + 1
                modifiedTimer = unmodifiedTimer + self.random_offset
                self.output(f"Step {self.step} - Áp dụng bù ngẫu nhiên cho bộ đếm thời gian chờ của: {self.random_offset} Phút.", 2)
                return modifiedTimer

        self.launch_iframe()

        xpath = "//button//span[contains(text(), 'Xác nhận ngay')]"
        button = self.move_and_click(xpath, 10, False, "nhấn vào 'Ocean Game' liên kết", self.step, "visible")
        self.driver.execute_script("arguments[0].click();", button)
        self.increase_step()

        self.get_balance(False)

        wait_time_text = self.get_wait_time(self.step, "pre-claim")

        if wait_time_text != self.pot_full:
            matches = re.findall(r'(\d+)([hm])', wait_time_text)
            remaining_wait_time = (sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
            if remaining_wait_time < 5 or self.settings["forceClaim"]:
                self.settings['forceClaim'] = True
                self.output(f"Bước {self.step} -thời gian còn lại để yêu cầu rất ngắn nên hãy yêu cầu dù sao đi nữa, vì vậy hãy đăng ký: settings['forceClaim'] = True", 3)
            else:
                remaining_wait_time += self.random_offset
                self.output(f"TÌNH TRẠNG: Xem xét {wait_time_text}, chúng tôi sẽ chuyển sang chế độ ngủ trong {remaining_wait_time} phút.", 1)
                return remaining_wait_time

        if wait_time_text == "không xác định":
            return 15

        try:
            self.output(f"Bước {self.step} -Thời gian chờ yêu cầu trước là: {wait_time_text} và thời gian bù trừ ngẫu nhiên là {self.random_offset} phút.", 1)
            self.increase_step()

            if wait_time_text == self.pot_full or self.settings['forceClaim']:
                try:
                    xpath = "//div[contains(text(), 'Xác nhận ngay')]"
                    button = self.move_and_click(xpath, 10, False, "nhấp vào nút yêu cầu", self.step, "Hiện tại")
                    try:
                        self.driver.execute_script("arguments[0].click();", button)
                        self.increase_step()
                    except Exception:
                        pass

                    self.output(f"Bước {self.step} -Hãy đợi spinner Yêu cầu đang chờ xử lý ngừng quay...", 2)
                    time.sleep(5)
                    wait = WebDriverWait(self.driver, 240)
                    spinner_xpath = "//*[contains(@class, 'spinner')]"
                    try:
                        wait.until(EC.invisibility_of_element_located((By.XPATH, spinner_xpath)))
                        self.output(f"Step {self.step} -  hành động spinner đang chờ xử lý đã dừng.\n", 3)
                    except TimeoutException:
                        self.output(f"Bước {self.step} -Có vẻ như trang web bị lag -Spinner không biến mất kịp thời.\n", 2)
                    self.increase_step()
                    wait_time_text = self.get_wait_time(self.step, "post-claim")
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    total_wait_time = apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                    self.increase_step()

                    self.get_balance(True)

                    if wait_time_text == self.pot_full:
                        self.output(f"TRẠNG THÁI: Đồng hồ chờ vẫn hiển thị: Đã đầy.", 1)
                        self.output(f"Bước {self.step} -Điều này có nghĩa là xác nhận quyền sở hữu không thành công hoặc có độ trễ >4 phút trong trò chơi.", 1)
                        self.output(f"Bước {self.step} -Chúng tôi sẽ kiểm tra lại sau 1 giờ để xem khiếu nại đã được xử lý chưa và nếu chưa hãy thử lại.", 2)
                    else:
                        self.output(f"TRẠNG THÁI: Xác nhận quyền sở hữu thành công: Yêu cầu tiếp theo {wait_time_text} /{total_wait_time} phút.", 1)
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

        balance_text = f'{prefix} Số dư:' if claimed else f'{prefix} Số dư:'
        xpath = "//p[contains(@class, 'wave-balance')]"

        try:
            element = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )

            balance_part = self.driver.execute_script("return arguments[0].textContent.trim();", element)
            
            if balance_part:
                self.output(f"Step {self.step} - {balance_text} {balance_part}", priority)
                return balance_part

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Phần tử chứa'{prefix} Số dư:' không tìm thấy.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)

        self.increase_step()

    def get_wait_time(self, step_number="108", beforeAfter="pre-claim", max_attempts=2):
        for attempt in range(1, max_attempts + 1):
            try:
                xpath = "//span[contains(@class, 'boat_balance')]"
                wait_time_element = self.move_and_click(xpath, 5, True, f"nhận được {beforeAfter} hẹn giờ chờ (time elapsing method)", self.step, "present")
                if wait_time_element is not None:
                    return wait_time_element.text
                xpath = "//div[contains(text(), 'Claim Now')]"
                wait_time_element = self.move_and_click(xpath, 10, False, f"nhận được {beforeAfter} hẹn giờ chờ (pot full method)", self.step, "present")
                if wait_time_element is not None:
                    return self.pot_full
                    
            except Exception as e:
                self.output(f"Bước {self.step} -Đã xảy ra lỗi khi thử {attempt}: {e}", 3)

        return "Unknown"

def main():
    claimer = WaveClaimer()
    claimer.run()

if __name__ == "__main__":
    main()