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

class ColdClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/cold.py"
        self.prefix = "BNB-Cold:"
        self.url = "https://web.telegram.org/k/#@Newcoldwallet_bot"
        self.pot_full = "Filled"
        self.pot_filling = "Mining"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False
        self.start_app_xpath = "//button//span[contains(text(), 'Open Wallet')]"

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

            #Cố gắng tương tác với các phần tử trong iframe.
#Trước tiên hãy nhấp vào nút đăng nhập:
            xpath = "//button[contains(text(), 'Log in')]"
            self.target_element = self.move_and_click(xpath, 20, False, "find log-in button (may not be present)", "08", "visible")
            self.driver.execute_script("arguments[0].click();", self.target_element)
            self.increase_step()

            self.set_cookies()

        except TimeoutException:
            self.output(f"Bước {self.step} -Không tìm thấy hoặc chuyển sang iframe trong khoảng thời gian chờ.",1)

        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}",1)

    def full_claim(self):
        self.step = "100"
        self.launch_iframe()

        #Nhấp vào liên kết Lưu trữ:
        xpath = "//h4[text()='Storage']"
        self.move_and_click(xpath, 30, True, "click the 'storage' link", self.step, "clickable")
        self.increase_step()

        self.get_balance(False)
        self.get_profit_hour(False)
        wait_time_text = self.get_wait_time(self.step, "pre-claim") 

        if wait_time_text != "Filled":
            self.output(f"TÌNH TRẠNG: Nồi chưa đầy, chúng ta sẽ quay lại ngủ 1 tiếng.", 1)
            return 60

        try:
            self.output(f"Bước {self.step} -Thời gian chờ yêu cầu trước là: {wait_time_text}", 1)
            self.increase_step()

            if wait_time_text == "Filled" or self.settings['forceClaim']:
                try:
                    original_window = self.driver.current_window_handle
                    xpath = "//button[contains(text(), 'Check News')]"
                    button = self.move_and_click(xpath, 10, True, "kiểm tra TIN TỨC (có thể không có mặt).", self.step, "clickable")
                    if button:
                        self.output(f"Bước {self.step} -Nhấp vào nút Kiểm tra tin tức...", 2)
                    self.driver.switch_to.window(original_window)
                    self.increase_step()
                    self.select_iframe(self.step)
                    self.increase_step()
                except TimeoutException:
                    if self.settings['debugIsOn']:
                        self.output(f"Bước {self.step} -Không có tin tức nào để kiểm tra hoặc không tìm thấy nút.", 3)

                #Một lần thử nhấp vào nút Yêu cầu
                try:
                    #Bấm vào nút "Yêu cầu":
                    xpath = "//button[contains(text(), 'Claim')]"
                    self.move_and_click(xpath, 10, True, "nhấp vào nút Claim đầu tiên", self.step, "clickable")
                    self.increase_step()

                    xpath = '//div[contains(@class, "react-responsive-modal-modal")]//button[contains(@class, "btn-primary") and text()="Claim"]'
                    self.move_and_click(xpath, 10, True, "nhấp vào nút Claim thứ 2", self.step, "clickable")
                    self.output(f"Step {self.step} - Đã nhấp vào nút Claim thứ 2...", 2)
                    self.increase_step()

                    #Đợi vòng quay biến mất trước khi cố gắng lấp đầy thời gian mới.
                    self.output(f"Bước {self.step} -Đợi vòng quay Yêu cầu đang chờ xử lý ngừng quay...", 2)
                    time.sleep(20)

                    self.get_balance(True)
                    self.get_profit_hour(True)
                    wait_time_text = self.get_wait_time(self.step, "post-claim")

                    if wait_time_text != "Filled":
                        self.output(f"TÌNH TRẠNG: Yêu cầu thành công: Chúng tôi sẽ kiểm tra lại hàng giờ để biết số tiền đã đầy.", 1)
                        return 60
                    else:
                        self.output(f"TRẠNG THÁI: Đồng hồ chờ vẫn hiển thị: Đã đầy", 1)
                        self.output(f"Step {self.step} - This means either the claim failed, or there is lag in the game.", 1)

                except TimeoutException:
                    self.output(f"TRẠNG THÁI: Quá trình xác nhận quyền sở hữu đã hết thời gian: Có thể trang web bị lag? Sẽ thử lại sau một giờ.", 1)
                    return 60
                except Exception as e:
                    self.output(f"TRẠNG THÁI: Đã xảy ra lỗi khi cố gắng xác nhận quyền sở hữu: {e}", 1)
                    return 60

            #Kiểm tra xem trạng thái có còn "Đã điền" bên ngoài khối thử không
            self.get_balance(True)
            self.get_profit_hour(True)
            wait_time_text = self.get_wait_time(self.step, "post-claim")
            if wait_time_text != "Filled":
                self.output(f"TÌNH TRẠNG: Yêu cầu thành công: Chúng tôi sẽ kiểm tra lại hàng giờ để biết số tiền đã đầy", 1)
                return 60

            self.output(f"Step {self.step} - Exhausted all claim attempts. We'll check back in 1 hour to see if the claim processed and if not try again.", 2)
            return 60

        except TimeoutException:
            self.output(f"TRẠNG THÁI: Quá trình xác nhận quyền sở hữu đã hết thời gian: Có thể trang web bị lag? Sẽ thử lại sau một giờ.", 1)
            return 60
        except Exception as e:
            self.output(f"TRẠNG THÁI: Đã xảy ra lỗi khi cố gắng xác nhận quyền sở hữu: {e}\nHãy đợi một giờ và thử lại", 1)
            return 60

    def get_balance(self, claimed=False):

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        #Tự động điều chỉnh mức độ ưu tiên của nhật ký
        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng số dư cụ thể XPath
        balance_text = f'{prefix} BALANCE:'
        balance_xpath = f"(//img[@alt='COLD']/following-sibling::p)[last()]"

        try:
            element = self.monitor_element(balance_xpath)

            #Kiểm tra xem phần tử có phải là Không và xử lý số dư
            if element:
                cleaned_balance = self.strip_html_and_non_numeric(element)
                self.output(f"Step {self.step} - {balance_text} {cleaned_balance}", priority)

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
        profit_xpath = "//div[p[text()='Frost Box']]//p[last()]"

        try:
            element = self.strip_non_numeric(self.monitor_element(profit_xpath))

            #Kiểm tra xem phần tử có phải là Không và xử lý lợi nhuận
            if element:
                self.output(f"Bước  {self.step} - {profit_text} {element}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Lợi nhuận/Giờ:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
#Hàm bước tăng dần, giả sử để xử lý logic bước tiếp theo
        self.increase_step()


    def get_wait_time(self, step_number="108", beforeAfter="pre-claim"):
        try:
            xpath = "//p[contains(text(), 'Filled')]"
            wait_time_element = self.move_and_click(xpath, 10, False, f"get the {beforeAfter} wait timer", step_number, "visible")

            #Kiểm tra xem Wait_time_element có phải là Không
            if wait_time_element is not None:
                return "Filled"
            else:
                return "Mining"
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {e}", 3)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}_get_wait_time_error.png"
                self.driver.save_screenshot(screenshot_path)
                self.output(f"Ảnh chụp màn hình đã được lưu vào {screenshot_path}", 3)
            return "không xác định"

def main():
    claimer = ColdClaimer()
    claimer.run()

if __name__ == "__main__":
    main()