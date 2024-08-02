import os
import shutil
import sys
import time
import re
import json
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

class HotClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/hot.py"
        self.prefix = "HOT:"
        self.url = "https://web.telegram.org/k/#@game-telegram-autobot"
        self.pot_full = "Filled"
        self.pot_filling = "to fill"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False
        self.step = "01"
        self.imported_seedphrase = None
        self.start_app_xpath = "//a[@href='https://t.me/herewalletbot/app']"

    def __init__(self):
        self.settings_file = "variables.txt"
        self.status_file_path = "status.txt"
        self.wallet_id = ""
        self.load_settings()
        self.random_offset = random.randint(self.settings['lowestClaimOffset'], self.settings['highestClaimOffset'])
        super().__init__()

    def next_steps(self):
        try:
            self.launch_iframe()
            self.increase_step()

            xpath = "//button[p[contains(text(), 'Log in')]]"
            target_element = self.move_and_click(xpath, 30, False, "find the HereWallet log-in button", "08", "visible")
            self.driver.execute_script("arguments[0].click();", target_element)
            self.increase_step()

            xpath = "//p[contains(text(), 'Seed or private key')]/ancestor-or-self::*/textarea"
            input_field = self.move_and_click(xpath, 30, True, "locate seedphrase textbox", self.step, "clickable")
            if not self.imported_seedphrase:
                self.imported_seedphrase = self.validate_seed_phrase()
            input_field.send_keys(self.imported_seedphrase) 
            self.output(f"Bước {self.step} -Đã nhập thành công cụm từ hạt giống...", 3)
            self.increase_step()

            xpath = "//button[contains(text(), 'Continue')]"
            self.move_and_click(xpath, 30, True, "click continue after seedphrase entry", self.step, "clickable")
            self.increase_step()

            xpath = "//button[contains(text(), 'Select account')]"
            self.move_and_click(xpath, 180, True, "click continue at account selection screen", self.step, "clickable")
            self.increase_step()

            xpath = "//h4[text()='Storage']"
            self.move_and_click(xpath, 30, True, "click the 'storage' link", self.step, "clickable")
            
            self.set_cookies()

        except TimeoutException:
            self.output(f"Bước {self.step} -Không tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.", 1)

        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}", 1)

    def full_claim(self):
        self.step = "100"

        self.launch_iframe()

        xpath = "//h4[text()='Storage']"
        self.move_and_click(xpath, 20, True, "click the 'storage' link", self.step, "clickable")

        self.increase_step()

        self.get_balance(False)
        self.get_profit_hour(False)

        wait_time_text = self.get_wait_time(self.step, "pre-claim") 

        if wait_time_text != "Filled":
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
            self.output(f"Bước {self.step} -Thời gian chờ yêu cầu trước là: {wait_time_text} và thời gian bù trừ ngẫu nhiên là {self.random_offset} phút.", 1)
            self.increase_step()

            if wait_time_text == "Filled" or self.settings['forceClaim']:
                try:
                    original_window = self.driver.current_window_handle
                    xpath = "//button[contains(text(), 'Check NEWS')]"
                    self.move_and_click(xpath, 3, True, "kiểm tra TIN TỨC.", self.step, "clickable")
                    self.driver.switch_to.window(original_window)
                except TimeoutException:
                    if self.settings['debugIsOn']:
                        self.output(f"Bước {self.step} -Không có tin tức nào để kiểm tra hoặc không tìm thấy nút.", 3)
                self.increase_step()

                try:
                    self.select_iframe(self.step)
                    self.increase_step()
                    
                    xpath = "//button[contains(text(), 'Claim HOT')]"
                    self.move_and_click(xpath, 30, True, "click the claim button", self.step, "clickable")
                    self.increase_step()

                    self.output(f"Bước {self.step} -Đợi Claim spinner đang chờ xử lý ...", 2)
                    time.sleep(5)
                    wait = WebDriverWait(self.driver, 240)
                    spinner_xpath = "//*[contains(@class, 'spinner')]" 
                    try:
                        wait.until(EC.invisibility_of_element_located((By.XPATH, spinner_xpath)))
                        self.output(f"Bước {self.step} -Vòng quay hành động đang chờ xử lý đã dừng.\n", 3)
                    except TimeoutException:
                        self.output(f"Bước {self.step} -Có vẻ như trang web bị lag -Spinner không biến mất kịp thời.\n", 2)
                    self.increase_step()
                    wait_time_text = self.get_wait_time(self.step, "post-claim") 
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    total_wait_time = self.apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                    self.increase_step()

                    self.get_balance(True)
                    self.get_profit_hour(True)

                    if wait_time_text == "Filled":
                        self.output(f"TRẠNG THÁI: Đồng hồ chờ vẫn hiển thị: Đã đầy", 1)
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
        balance_text = f'{prefix} BALANCE:' if claimed else f'{prefix} BALANCE:'
        balance_xpath = f"//p[contains(text(), 'HOT')]/following-sibling::img/following-sibling::p"

        try:
            element = self.monitor_element(balance_xpath)
            if element:
                balance_part = element #.text.strip()
                self.output(f"Step {self.step} - {balance_text} {balance_part}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)

        self.increase_step()

    def get_profit_hour(self, claimed=False):
        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng lợi nhuận cụ thể XPath
        profit_text = f'{prefix} PROFIT/HOUR:'
        profit_xpath = "//div[div[p[text()='Storage']]]//p[last()]"

        try:
            element = self.strip_non_numeric(self.monitor_element(profit_xpath))

            #Kiểm tra xem phần tử có phải là Không và xử lý lợi nhuận
            if element:
                self.output(f"Step {self.step} - {profit_text} {element}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Lợi nhuận/Giờ:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
        
        self.increase_step()

    def get_wait_time(self, step_number="108", beforeAfter="pre-claim", max_attempts=2):
        for attempt in range(1, max_attempts + 1):
            try:
                xpath = f"//div[contains(., 'Storage')]//p[contains(., '{self.pot_full}') or contains(., '{self.pot_filling}')]"
                wait_time_element = self.move_and_click(xpath, 20, True, f"get the {beforeAfter} wait timer", self.step, "visible")
                if wait_time_element is not None:
                    return wait_time_element.text
                else:
                    self.output(f"Bước {self.step} -Cố gắng {attempt}: Không tìm thấy phần tử thời gian chờ. Nhấp vào liên kết 'Storage' và thử lại...", 3)
                    storage_xpath = "//h4[text()='Storage']"
                    self.move_and_click(storage_xpath, 30, True, "nhấp vào liên kết 'storage'", f"{self.step} recheck", "clickable")
                    self.output(f"Step {self.step} - Đã cố gắng chọn lại bộ nhớ...", 3)
                return wait_time_element.text

            except TimeoutException:
                if attempt < max_attempts:
                    self.output(f"Bước {self.step} -Cố gắng {attempt}: Không tìm thấy phần tử thời gian chờ. Nhấp vào liên kết 'Storage' và thử lại...", 3)
                    storage_xpath = "//h4[text()='Storage']"
                    self.move_and_click(storage_xpath, 30, True, "nhấp vào liên kết 'storage'", f"{self.step} recheck", "clickable")
                else:
                    self.output(f"Bước {self.step} -Cố gắng {attempt}: Không tìm thấy phần tử thời gian chờ.", 3)

            except Exception as e:
                self.output(f"Bước {self.step} -Đã xảy ra lỗi khi thử {attempt}: {e}", 3)

        return "không xác định"

def main():
    claimer = HotClaimer()
    claimer.run()

if __name__ == "__main__":
    main()
