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

from fuel import FuelClaimer

class FuelAUClaimer(FuelClaimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/fuel-autoupgrade.py"
        self.prefix = "Fuel-Auto:"
        self.ad_cycle = 1

    def __init__(self):
        super().__init__()
        self.start_app_xpath = "//span[contains(text(), 'Start pumping oil')]"

    def recycle_and_upgrade(self):
        steps = [
            {"xpath": "//a[text()='Recycling']", "button_text": "click the 'Recycling' button"},
            {"xpath": "//button[@class='recycle-button']", "button_text": "Refining Oil to Fuel"},
        ]

        for step_info in steps:
            success = self.move_and_click(step_info["xpath"], 10, True, step_info["button_text"], self.step, "clickable")
            if success:
                self.output(f"Step {self.step} - Successfully: {step_info['button_text']}", 2)
                self.increase_step()
                time.sleep(10)
            else:
                self.output(f"Step {self.step} - Failed: Unable to {step_info['button_text']}", 2)
                self.handle_recycling_failure(self.step)

        fuel_amount = self.get_fuel_amount()
        self.output(f"Step {self.step} - Fuel amount: {fuel_amount}", 2)

    def handle_recycling_failure(self, step):
        xpath = "//div[@class='c-ripple']"
        self.move_and_click(xpath, 10, True, "click the 'btn-icon popup-close' button", step, "clickable")
        xpath = "//div[@class='btn-menu bottom-left active was-open']"
        success = self.move_and_click(xpath, 10, True, "click the 'btn-icon popup-close' button", step, "clickable")
        if success:
            self.output(f"Step {step} - Successfully: exit", 2)
        self.driver.quit()
        return

    def get_fuel_amount(self):
        xpath = "//span[@class='fuel-balance']"
        success = self.move_and_click(xpath, 10, False, "look for fuel amount", self.step, "visible")
        if success:
            element = self.driver.find_element(By.XPATH, xpath)
            fuel_amount = element.text
            return fuel_amount
        return 0

    def upgrade_cost(self):
        buttons = [
            ("//a[text()='Upgrades']", "click the 'Upgrades' button"),
            ("//button[@class='mining-card-button']", "click the 'Upgrade prod' button")
        ]

        for xpath, button_text in buttons:
            if self.move_and_click(xpath, 10, True, button_text, self.step, "clickable"):
                self.output(f"Step {self.step} - Successfully: {button_text}", 2)

        upgrade_button_xpath = "//button[contains(@class, 'miner-modal-button')]"
        upgrade_button = self.move_and_click(upgrade_button_xpath, 30, False, "look for Upgrade cost", self.step, "visible")
        
        if upgrade_button:
            button_text = self.driver.find_element(By.XPATH, upgrade_button_xpath).text

            match = re.search(r"Upgrade for (\d+)", button_text)
            if match:
                upgrade_cost = int(match.group(1))
                fuel_amount = int(self.get_fuel_amount())
                fuel_missing = upgrade_cost - fuel_amount

                if fuel_missing > 0:
                    fuel_text = f", shortfall of {fuel_missing}"
                else:
                    fuel_text = "."

                self.output(f"Step {self.step} - Upgrade cost: {upgrade_cost}, your fuel {fuel_amount}{fuel_text}", 2)

                if fuel_amount >= upgrade_cost:
                    if self.move_and_click(upgrade_button_xpath, 10, True, "click the 'Upgrade' button", self.step, "clickable"):
                        self.output(f"Step {self.step} - Successfully upgraded", 2)
                    else:
                        self.output(f"Step {self.step} - Failed to upgrade", 2)
                else:
                    self.output(f"Step {self.step} - Not enough fuel to upgrade", 2)

                self.launch_iframe()

                return upgrade_cost

        return 0

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
                    if self.ad_cycle % 12 == 1:
                        self.upgrade_cost()
                    else:
                        self.adverts()

                    self.output(f"TRẠNG THÁI: Chưa hết hạn trong {remaining_wait_time} phút -hãy quay lại sau 30 phút nữa để kiểm tra quảng cáo.", 1)
                    return 30
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
                    self.move_and_click(xpath, 10, True, "nhấp vào nút 'Send to warehouse'", self.step, "clickable")
                    self.output(f"Bước {self.step} -Chờ 10 giây để cập nhật tổng số và bộ hẹn giờ...", 3)
                    time.sleep(10)
                    wait_time_text = self.get_wait_time(self.step, "post-claim")
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    total_wait_time = self.apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                    self.recycle_and_upgrade()
                    self.increase_step()
                    self.quit_driver()
                    self.launch_iframe()
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
                        self.adverts()
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


def main():
    claimer = FuelAUClaimer()
    claimer.run()

if __name__ == "__main__":
    main()