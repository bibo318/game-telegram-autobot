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
                self.output(f"Step {self.step} - the remaining time to claim is less than the random offset, so applying: settings['forceClaim'] = True", 3)
            else:
                self.output(f"STATUS: Considering {wait_time_text}, we'll go back to sleep for {remaining_wait_time} minutes.", 1)
                return remaining_wait_time

        if wait_time_text == "Unknown":
            return 15

        try:
            self.output(f"Step {self.step} - The pre-claim wait time is : {wait_time_text} and random offset is {self.random_offset} minutes.", 1)
            self.increase_step()

            if wait_time_text == self.pot_full or self.settings['forceClaim']:
                try:
                    xpath = "//div[@class='farm_btn']"
                    button = self.move_and_click(xpath, 10, True, "click the 'Claim' button", self.step, "clickable")
                    self.increase_step()

                    self.output(f"Step {self.step} - Waiting 10 seconds for the totals and timer to update...", 3)
                    time.sleep(10)
                    self.increase_step()
                    
                    self.click_daily_buttons()
                    self.increase_step()

                    self.output(f"Step {self.step} - Waiting 10 seconds for the totals and timer to update...", 3)
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
                        self.output(f"STATUS: The wait timer is still showing: Filled.", 1)
                        self.output(f"Step {self.step} - This means either the claim failed, or there is lag in the game.", 1)
                        self.output(f"Step {self.step} - We'll check back in 1 hour to see if the claim processed and if not try again.", 2)
                    else:
                        self.output(f"STATUS: Successful Claim: Next claim {wait_time_text} / {total_wait_time} minutes.", 1)
                    return max(60, total_wait_time)

                except TimeoutException:
                    self.output(f"STATUS: The claim process timed out: Maybe the site has lag? Will retry after one hour.", 1)
                    return 60
                except Exception as e:
                    self.output(f"STATUS: An error occurred while trying to claim: {e}\nLet's wait an hour and try again", 1)
                    return 60

            else:
                matches = re.findall(r'(\d+)([hm])', wait_time_text)
                if matches:
                    total_time = sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)
                    total_time += 1
                    total_time = max(5, total_time) 
                    self.output(f"Step {self.step} - Not Time to claim this wallet yet. Wait for {total_time} minutes until the storage is filled.", 2)
                    return total_time 
                else:
                    self.output(f"Step {self.step} - No wait time data found? Let's check again in one hour.", 2)
                    return 60
        except Exception as e:
            self.output(f"Step {self.step} - An unexpected error occurred: {e}", 1)
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
            self.output(f"Step {self.step} - Element containing '{prefix} Balance:' was not found.", priority)
        except Exception as e:
            self.output(f"Step {self.step} - An error occurred: {str(e)}", priority)

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