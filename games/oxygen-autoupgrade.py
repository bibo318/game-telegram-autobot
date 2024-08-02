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

from oxygen import OxygenClaimer

from oxygen import OxygenClaimer
import random
import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

class OxygenAUClaimer(OxygenClaimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/oxygen-autoupgrade.py"
        self.prefix = "Oxygen-Auto:"

    def __init__(self):
        super().__init__()
        self.start_app_xpath = "//div[contains(@class, 'reply-markup-row')]//button[.//span[contains(text(), 'Start App')] or .//span[contains(text(), 'Play Now!')]]"
        self.new_cost_oxy = None
        self.new_cost_food = None
        self.oxy_upgrade_success = None
        self.food_upgrade_success = None

    def full_claim(self):
        self.step = "100"

        self.launch_iframe()
        self.increase_step()

        self.get_balance(True)
        self.increase_step()

        self.output(f"Step {self.step} - The last lucky box claim was attempted on {self.box_claim}.", 2)
        self.increase_step()

        wait_time_text = self.get_wait_time(self.step, "pre-claim") 

        if wait_time_text != self.pot_full:
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

            if wait_time_text == self.pot_full or self.settings['forceClaim']:
                try:
                    xpath = "//div[@class='farm_btn']"
                    button = self.move_and_click(xpath, 10, True, "nhấp vào nút 'Claim", self.step, "clickable")
                    self.increase_step()

                    self.output(f"Bước {self.step} -Chờ 10 giây để cập nhật tổng số và bộ hẹn giờ...", 3)
                    time.sleep(10)
                    self.increase_step()
                    
                    self.click_daily_buttons()
                    self.increase_step()

                    self.output(f"Bước {self.step} -Chờ 10 giây để cập nhật tổng số và bộ hẹn giờ...", 3)
                    time.sleep(10)

                    wait_time_text = self.get_wait_time(self.step, "post-claim")
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    calculated_time = sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)
                    random_offset = self.apply_random_offset(calculated_time)

                    total_wait_time = random_offset if random_offset > calculated_time else calculated_time

                    self.increase_step()

                    self.get_balance(True)
                    self.increase_step()
                    self.quit_driver()
                    self.launch_iframe()
                    self.output(f"Step {self.step} - check if there are lucky boxes..", 3)
                    xpath = "//div[@class='boxes_cntr']"
                    boxes = self.monitor_element(xpath)
                    self.output(f"Step {self.step} - Detected there are {boxes} boxes to claim.", 3)
                    if int(boxes) > 0:
                        xpath = "//div[@class='boxes_d_wrap']"
                        self.move_and_click(xpath, 10, True, "click the boxes button", self.step, "clickable")
                        xpath = "//div[@class='boxes_d_open' and contains(text(), 'Open box')]"
                        box = self.move_and_click(xpath, 10, True, "open the box...", self.step, "clickable")
                        if box:
                            self.box_claim = datetime.now().strftime("%d %B %Y, %I:%M %p")
                            self.output(f"Step {self.step} - The date and time of the box claim has been updated to {self.box_claim}.", 3)

                    if wait_time_text == self.pot_full:
                        self.output(f"TRẠNG THÁI: Đồng hồ chờ vẫn hiển thị: Đã đầy", 1)
                        self.output(f"Step {self.step} - This means either the claim failed, or there is lag in the game.", 1)
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

        balance_text = f'{prefix} BALANCE:'
        oxy_xpath = "//span[@class='oxy_counter']"
        food_xpath = "//div[@class='indicator_item' and @data='food']/div[@class='indicator_text']"

        try:
            oxy_balance = self.monitor_element(oxy_xpath)
            food_balance = self.monitor_element(food_xpath)

            self.output(f"Step {self.step} - {balance_text} Oxygen: {oxy_balance}, Food: {food_balance}", priority)

            boost_xpath = "(//div[@class='menu_item' and @data='boosts']/div[@class='menu_icon icon_boosts'])[1]"
            self.move_and_click(boost_xpath, 10, True, "click the boost button", self.step, "clickable")

            cost_oxy_xpath = "//span[@class='upgrade_price oxy_upgrade']"
            cost_food_xpath = "//span[@class='upgrade_price']"

            initial_cost_oxy = self.monitor_element(cost_oxy_xpath)
            initial_cost_food = self.monitor_element(cost_food_xpath)

            self.output(f"Step {self.step} - Initial Oxygen upgrade cost: {initial_cost_oxy} & Initial Food upgrade cost: {initial_cost_food}", 3)

            self.attempt_upgrade('oxygen', oxy_balance, initial_cost_oxy, cost_oxy_xpath)
            self.attempt_upgrade('food', food_balance, initial_cost_food, cost_food_xpath)

            close_page_button_xpath = "//div[@class='page_close']"
            self.move_and_click(close_page_button_xpath, 10, True, "close the pop-up", self.step, "clickable")

            return {
                'oxy': oxy_balance,
                'food': food_balance,
                'initial_cost_oxy': initial_cost_oxy,
                'initial_cost_food': initial_cost_food,
                'new_cost_oxy': self.new_cost_oxy,
                'new_cost_food': self.new_cost_food,
                'oxy_upgrade_success': self.oxy_upgrade_success,
                'food_upgrade_success': self.food_upgrade_success
            }

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)

        self.increase_step()

        return None

    def attempt_upgrade(self, resource_name, balance, initial_cost, cost_xpath):
        try:
            balance = float(balance)
            initial_cost = float(initial_cost)

            if balance >= initial_cost:
                click_xpath = f"//div[@class='upgrade_btn' and @data='{resource_name}'][1]"
                upgrade_element = self.move_and_click(click_xpath, 10, True, f"click the {resource_name} upgrade button", self.step, "clickable")
                new_cost = float(self.monitor_element(cost_xpath))
                upgrade_success = "Success" if new_cost != initial_cost else "Failed"
                self.output(f"Step {self.step} - {resource_name.capitalize()} upgrade: {upgrade_success}", 3)
                setattr(self, f'new_cost_{resource_name}', new_cost)
                setattr(self, f'{resource_name}_upgrade_success', upgrade_success)
            else:
                shortfall = initial_cost - balance
                self.output(f"Step {self.step} - Not enough {resource_name.capitalize()} to upgrade, shortfall of: {shortfall}", 3)
        except ValueError as e:
            self.output(f"Step {self.step} - Error: Invalid value encountered for {resource_name} upgrade. Details: {str(e)}", 3)

def main():
    claimer = OxygenAUClaimer()
    claimer.run()

if __name__ == "__main__":
    main()