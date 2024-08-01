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

class SeedClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/seed.py"
        self.prefix = "Seed:"
        self.url = "https://web.telegram.org/k/#@seed_coin_bot"
        self.pot_full = "Filled"
        self.pot_filling = "to fill"
        self.seed_phrase = None
        self.forceLocalProxy = False
        self.forceRequestUserAgent = False

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

            cookies_path = f"{self.session_path}/cookies.json"
            cookies = self.driver.get_cookies()
            with open(cookies_path, 'w') as file:
                json.dump(cookies, file)

        except TimeoutException:
            self.output(f"Step {self.step} - Failed to find or switch to the iframe within the timeout period.",1)

        except Exception as e:
            self.output(f"Step {self.step} - An error occurred: {e}",1)

    def full_claim(self):
        self.step = "100"
            
        self.launch_iframe()

        xpath = "//button[contains(text(), 'Claim')]"
        self.move_and_click(xpath, 20, True, "check for Mystery Box (may not be present)", self.step, "clickable")

        xpath = "//div[contains(text(), 'Tap 10')]"    
        self.move_and_click(xpath, 10, True, "check if tree tap blocking game (may not be present)", self.step, "clickable")
        self.increase_step()

        xpath = "//button[contains(text(), 'CHECK NEWS')]"
        self.move_and_click(xpath, 20, True, "check for NEWS (may not be present)", self.step, "clickable")
        
        #NHẬN GIỮA
        xpath = "//img[contains(@src,'inventory/worm')]"
        self.move_and_click(xpath, 20, True, "check for WORM (may not be present)", self.step, "clickable")

        xpath = "//button[.//p[contains(text(), 'Sell now')]]"
        self.move_and_click(xpath, 20, True, "sell WORM (may not be present)", self.step, "clickable")
        
        #NHẬN TIỀN THƯỞNG HÀNG NGÀY
        xpath = "//button[.//img[contains(@src, 'daily')]]"
        self.move_and_click(xpath, 20, True, "check for DAILY BONUS (may not be present)", self.step, "clickable")

        xpath = "//button[count(.//img) = 1 and .//img[contains(@src, 'daily/')]]"
        self.move_and_click(xpath, 20, True, "get DAILY BONUS (may not be present)", self.step, "clickable")

        xpath = "//button[contains(text(), 'Got it')]"
        self.move_and_click(xpath, 20, True, "exit DAILY BONUS (may not be present)", self.step, "clickable")

        self.get_balance(False)
        self.get_profit_hour(False)

        wait_time_text = self.get_wait_time(self.step, "pre-claim") 

        if wait_time_text != "Filled":
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

            if wait_time_text == "Filled" or self.settings['forceClaim']:
                try:
                    xpath = "//button[contains(text(), 'Claim')]"
                    button = self.move_and_click(xpath, 10, True, "click the 'Claim' button", self.step, "clickable")
                    self.increase_step()

                    #Bây giờ hãy cho trang web một vài giây để cập nhật.
                    self.output(f"Step {self.step} - Waiting 10 seconds for the totals and timer to update...", 3)
                    time.sleep(10)

                    wait_time_text = self.get_wait_time(self.step, "post-claim")
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    total_wait_time = self.apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                    self.increase_step()

                    self.get_balance(True)
                    self.get_profit_hour(True)

                    if wait_time_text == "Filled":
                        self.output(f"STATUS: The wait timer is still showing: Filled.", 1)
                        self.output(f"Step {self.step} - This means either the claim failed, or there is >4 minutes lag in the game.", 1)
                        self.output(f"Step {self.step} - We'll check back in 1 hour to see if the claim processed and if not try again.", 2)
                    else:
                        self.output(f"STATUS: Successful Claim: Next claim {wait_time_text} / {total_wait_time} minutes.",1)
                    return max(60, total_wait_time)

                except TimeoutException:
                    self.output(f"STATUS: The claim process timed out: Maybe the site has lag? Will retry after one hour.", 1)
                    return 60
                except Exception as e:
                    self.output(f"STATUS: An error occurred while trying to claim: {e}\nLet's wait an hour and try again", 1)
                    return 60

            else:
                #Nếu ví chưa sẵn sàng để nhận, hãy tính thời gian chờ dựa trên bộ đếm thời gian được cung cấp trên trang
                matches = re.findall(r'(\d+)([hm])', wait_time_text)
                if matches:
                    total_time = sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)
                    total_time += 1
                    total_time = max(5, total_time)  #Đợi ít nhất 5 phút hoặc thời gian
                    self.output(f"Step {self.step} - Not Time to claim this wallet yet. Wait for {total_time} minutes until the storage is filled.", 2)
                    return total_time
                else:
                    self.output(f"Step {self.step} - No wait time data found? Let's check again in one hour.", 2)
                    return 60  #Thời gian chờ mặc định khi không tìm thấy thời gian cụ thể cho đến khi được lấp đầy.
        except Exception as e:
            self.output(f"Step {self.step} - An unexpected error occurred: {e}", 1)
            return 60  #Thời gian chờ mặc định trong trường hợp xảy ra lỗi không mong muốn

    def get_balance(self, claimed=False):

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        #Tự động điều chỉnh mức độ ưu tiên của nhật ký
        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng số dư cụ thể XPath
        balance_text = f'{prefix} BALANCE:'
        balance_xpath = "//div[p[contains(text(), 'SEED Balance:')]]"

        try:
            element = self.monitor_element(balance_xpath)
            if isinstance(element, str):
                #Tách phần tử tại dấu hai chấm (nếu có) và gán vế phải (không bao gồm ://)
                if ':' in element:
                    element = element.split(':')[1].strip()
            #Kiểm tra xem phần tử có phải là Không và xử lý số dư
            if element:
                balance_part = element
                self.output(f"Step {self.step} - {balance_text} {balance_part}", priority)

        except NoSuchElementException:
            self.output(f"Step {self.step} - Element containing '{prefix} Balance:' was not found.", priority)
        except Exception as e:
            self.output(f"Step {self.step} - An error occurred: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
#Hàm bước tăng dần, giả sử để xử lý logic bước tiếp theo
        self.increase_step()

    def get_profit_hour(self, claimed=False):

        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        #Tự động điều chỉnh mức độ ưu tiên của nhật ký
        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng lợi nhuận cụ thể XPath
        profit_text = f'{prefix} PROFIT/HOUR:'
        profit_xpath = "//p[contains(text(), 'SEED/hour')]"

        try:
            element = self.monitor_element(profit_xpath)
            if isinstance(element, str):
                #Tách phần tử tại dấu hai chấm (nếu có) và gán vế phải (không bao gồm ://)
                if ' ' in element:
                    element = element.split(' ')[0].strip()
            #Kiểm tra xem phần tử có phải là Không và xử lý số dư
            if element:
                profit_part = element
                self.output(f"Step {self.step} - {profit_text} {profit_part}", priority)

        except NoSuchElementException:
            self.output(f"Step {self.step} - Element containing '{prefix} Profit/Hour:' was not found.", priority)
        except Exception as e:
            self.output(f"Step {self.step} - An error occurred: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
#Hàm bước tăng dần, giả sử để xử lý logic bước tiếp theo
        self.increase_step()


    def click_element(self, xpath, timeout=30, action_description=""):
        self.move_and_click(xpath, 8, False, f"move to {xpath}", self.step, "clickable")
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                #Đợi phần tử xuất hiện và có thể nhấp vào
                element = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                #Đảm bảo phần tử nằm trong khung nhìn
                self.driver.execute_script("arguments[0].scrollIntoView();", element)
                
                #Xóa mọi lớp phủ tiềm năng trước khi thử nhấp vào
                overlays_cleared = self.clear_overlays(element, self.step)
                if overlays_cleared > 0:
                    self.output(f"Step {self.step} - Cleared {overlays_cleared} overlay(s), retrying click...", 3)

                #Cố gắng nhấp vào phần tử
                self.driver.execute_script("arguments[0].click();", element)
                return True  #Thành công khi nhấp vào phần tử
            except ElementClickInterceptedException:
                pass #Hãy quay lại vì vẫn còn lớp phủ
            except (StaleElementReferenceException, NoSuchElementException):
                self.output(f"Step {self.step} - Element not found or stale, retrying...", 3)
                pass  #Không tìm thấy phần tử hoặc phần tử cũ, hãy thử lại
            except TimeoutException:
                self.output(f"Step {self.step} - Click timed out.", 3)
                break  #Hết giờ -chúng ta hãy quay lại.
            except Exception as e:
                self.output(f"Step {self.step} - An error occurred: {e}", 3)
                break  #Thoát khỏi vòng lặp do lỗi không mong muốn
        return False  #Trả về Sai nếu không thể nhấp vào phần tử
#def move_and_click(self, xpath, wait_time, click, action_description, old_step, ExpectedCondition):

        self.target_element = None

        def timer():
            return random.randint(1, 3) / 10

        def offset():
            return random.randint(1, 5)

        self.output(f"Step {self.step} - Attempting to {action_description}...", 2)

        try:
            wait = WebDriverWait(self.driver, wait_time)
            #Kiểm tra và chuẩn bị phần tử dựa trên điều kiện dự kiến
            if expectedCondition == "visible":
                self.target_element = wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
            elif expectedCondition == "present":
                self.target_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            elif expectedCondition == "invisible":
                wait.until(EC.invisibility_of_element_located((By.XPATH, xpath)))
                return None  #Hoàn trả sớm vì không có yếu tố nào để tương tác
            elif expectedCondition == "clickable":
                self.target_element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))

            #Kiểm tra xem target_element có được tìm thấy không
            if self.target_element is None:
                self.output(f"Step {self.step} - The element was not found for {action_description}.", 2)
                return None

            #Trước khi tương tác, hãy kiểm tra và xóa lớp phủ nếu cần nhấp chuột hoặc cần hiển thị
            if expectedCondition in ["visible", "clickable"]:
                self.clear_overlays(self.target_element, self.step)

            #Thực hiện các hành động nếu tìm thấy phần tử và yêu cầu nhấp chuột
            if self.target_element:
                if expectedCondition == "clickable":
                    actions = ActionChains(self.driver)
                    actions.move_by_offset(0, 0 - offset()) \
                            .pause(timer()) \
                            .move_by_offset(0, offset()) \
                            .pause(timer()) \
                            .move_to_element(self.target_element) \
                            .pause(timer()) \
                            .perform()
                    self.output(f"Step {self.step} - Successfully moved to the element using ActionChains.", 3)
                if click:
                    self.click_element(xpath, wait_time)
            return self.target_element

        except TimeoutException:
            self.output(f"Step {self.step} - Timeout while trying to {action_description}.", 3)
            if self.settings['debugIsOn']:
                #Chụp nguồn trang và lưu nó vào một tập tin
                page_source = self.driver.page_source
                with open(f"{self.screenshots_path}/{self.step}_page_source.html", "w", encoding="utf-8") as f:
                    f.write(page_source)
                logs = self.driver.get_log("browser")
                with open(f"{self.screenshots_path}/{self.step}_browser_console_logs.txt", "w", encoding="utf-8") as f:
                    for log in logs:
                        f.write(f"{log['level']}: {log['message']}\n")

        except StaleElementReferenceException:
            self.output(f"Step {self.step} - StaleElementReferenceException caught for {action_description}.", 2)

        except Exception as e:
            self.output(f"Step {self.step} - An error occurred while trying to {action_description}: {e}", 1)

        finally:
            if self.settings['debugIsOn']:
                time.sleep(5)
                screenshot_path = f"{self.screenshots_path}/{self.step}-{action_description}.png"
                self.driver.save_screenshot(screenshot_path)
            return self.target_element

    def monitor_element(self, xpath, timeout=8):
        end_time = time.time() + timeout
        first_time = True
        while time.time() < end_time:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                #Gỡ lỗi: Xuất ra số phần tử được tìm thấy
                if first_time:
                    self.output(f"Step {self.step} - Found {len(elements)} elements with XPath: {xpath}", 3)
                    first_time = False

                #Lấy nội dung văn bản của tất cả các phần tử div có liên quan
                texts = []

                #Lặp lại từng phần tử và làm sạch văn bản trước khi thêm vào danh sách
                for element in elements:
                    if element.text.strip() != "":
                        cleaned_text = element.text.replace('\n', ' ').replace('\r', ' ').strip()
                        texts.append(cleaned_text)

                if texts:
                    combined_text = ' '.join(texts)
                    return combined_text
            except (StaleElementReferenceException, TimeoutException, NoSuchElementException):
                pass
            except Exception as e:
                self.output(f"An error occurred: {e}", 3)
            time.sleep(0.05)  #Ngủ ngắn để tránh bận rộn chờ đợi
        return "Unknown"

    def get_wait_time(self, step_number="108", beforeAfter="pre-claim", max_attempts=1):

        for attempt in range(1, max_attempts + 1):
            try:
                self.output(f"Step {self.step} - Get the wait time...", 3)
                xpath = "//div[p[text() = 'Storage']]/div[1]"
                elements = self.monitor_element(xpath, 10)
                #Thay thế các lần xuất hiện của " h" bằng "h" và " m" bằng "m" (bao gồm cả khoảng trắng)
                elements = elements.replace(" h ", "h ").replace(" m ", "m ")
                if elements:
                    return elements
                return "Unknown"
            except Exception as e:
                self.output(f"Step {self.step} - An error occurred on attempt {attempt}: {e}", 3)
                return "Unknown"

        #Nếu mọi nỗ lực đều thất bại
        return "Unknown"

    def find_working_link(self, old_step):

        self.output(f"Step {self.step} - Attempting to open a link for the app...",2)

        start_app_xpath = "//div[contains(@class, 'reply-markup-row')]//button[.//span[contains(text(), 'Open app') or contains(text(), 'Play')]]"
        try:
            start_app_buttons = WebDriverWait(self.driver, 5).until(EC.presence_of_all_elements_located((By.XPATH, start_app_xpath)))
            clicked = False

            for button in reversed(start_app_buttons):
                actions = ActionChains(self.driver)
                actions.move_to_element(button).pause(0.2)
                try:
                    if self.settings['debugIsOn']:
                        self.driver.save_screenshot(f"{self.screenshots_path}/{self.step} - Find working link.png".format(self.screenshots_path))
                    actions.perform()
                    self.driver.execute_script("arguments[0].click();", button)
                    clicked = True
                    break
                except StaleElementReferenceException:
                    continue
                except ElementClickInterceptedException:
                    continue

            if not clicked:
                self.output(f"Step {self.step} - None of the 'Open Wallet' buttons were clickable.\n",1)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-no-clickable-button.png"
                    self.driver.save_screenshot(screenshot_path)
                return False
            else:
                self.output(f"Step {self.step} - Successfully able to open a link for the app..\n",3)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-app-opened.png"
                    self.driver.save_screenshot(screenshot_path)
                return True

        except TimeoutException:
            self.output(f"Step {self.step} - Failed to find the 'Open Wallet' button within the expected timeframe.\n",1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-timeout-finding-button.png"
                self.driver.save_screenshot(screenshot_path)
            return False
        except Exception as e:
            self.output(f"Step {self.step} - An error occurred while trying to open the app: {e}\n",1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-unexpected-error-opening-app.png"
                self.driver.save_screenshot(screenshot_path)
            return False

    def find_claim_link(self, old_step):

        self.output(f"Step {self.step} - Attempting to open a link for the app...", 2)

        #Sửa đổi phần tử lớn hơn:
#Button_xpath = "//button[contains(@class, 'kit-button is-large is-secondary is-fill is-centered Button is-active')]"
#Đợi nút hiển thị
## nút_element = WebDriverWait(driver, 10).until(
## EC.visibility_of_element_located((By.XPATH, Button_xpath))
## )
## nếu nút_element:
## driver.execute_script("arguments[0].removeAttribution('style');", Button_element)
#Đã cập nhật để sử dụng bộ chọn CSS chung hơn
        start_app_xpath = "//button[contains(text(), 'Claim')]/.."
        try:
            start_app_buttons = WebDriverWait(self.driver, 5).until(EC.presence_of_all_elements_located((By.XPATH, start_app_xpath)))
            #Các nút lọc để tìm nút có văn bản cụ thể
            start_app_buttons = [btn for btn in start_app_buttons]

            clicked = False

            for button in reversed(start_app_buttons):
                actions = ActionChains(self.driver)
                actions.move_to_element(button).pause(0.2)
                try:
                    if self.settings['debugIsOn']:
                        self.driver.save_screenshot(f"{self.screenshots_path}/{self.step} - Find working link.png")
                    actions.perform()
                    self.driver.execute_script("arguments[0].click();", button)
                    clicked = True
                    break
                except StaleElementReferenceException:
                    continue
                except ElementClickInterceptedException:
                    continue

            if not clicked:
                self.output(f"Step {self.step} - None of the 'Claim' buttons were clickable.\n", 1)
                if self.settings['debugIsOn']:
                    self.screenshot_path = f"{self.screenshots_path}/{self.step}-no-clickable-button.png"
                    self.driver.save_screenshot(screenshot_path)
                return False
            else:
                self.output(f"Step {self.step} - Successfully able to open a link for the app..\n", 3)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-app-opened.png"
                    self.driver.save_screenshot(screenshot_path)
                return True

        except TimeoutException:
            self.output(f"Step {self.step} - Failed to find the 'Claim' button within the expected timeframe.\n", 1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-timeout-finding-button.png"
                self.driver.save_screenshot(screenshot_path)
            return False
        except Exception as e:
            self.output(f"Step {self.step} - An error occurred while trying to open the app: {e}\n", 1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-unexpected-error-opening-app.png"
                self.driver.save_screenshot(screenshot_path)
            return False


def main():
    claimer = SeedClaimer()
    claimer.run()

if __name__ == "__main__":
    main()
