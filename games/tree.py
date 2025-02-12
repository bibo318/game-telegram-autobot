import os
import time
import re
import json
import random
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException, ElementClickInterceptedException

from claimer import Claimer

class TreeClaimer(Claimer):

    def initialize_settings(self):
        super().initialize_settings()
        self.script = "games/tree.py"
        self.prefix = "TreeClaimer:"
        self.url = "https://www.treemine.app/login"
        self.pot_full = "0h 0m to fill"
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

    def check_login(self):
        xpath = "//p[contains(text(), 'Seed phrase')]/ancestor-or-self::*/textarea"
        input_field = self.move_and_click(xpath, 5, True, "locate seedphrase textbox", self.step, "clickable")
        
        if input_field:
            seed_phrase = self.get_seed_phrase_from_file(self.screenshots_path)
            
            if not seed_phrase and int(self.step) < 100:
                seed_phrase = self.validate_seed_phrase()
                self.output("WARNING: Your seedphrase will be saved as an unencrypted file on your local filesystem if you choose 'y'!",1)
                save_to_file = input("Would you like to save the validated seed phrase to a text file? (y/N): ")
                if save_to_file.lower() == 'y':
                    seed_file_path = os.path.join(self.screenshots_path, 'seed.txt')
                    with open(seed_file_path, 'w') as file:
                        file.write(seed_phrase)
                    self.output(f"Seed phrase saved to {seed_file_path}", 3)
            if not seed_phrase and int(self.step) > 99:
                session = self.session_path.replace("./selenium/", "")
                self.output (f"Step {self.step} - You have become logged out: use './launch.sh tree {session} reset' from the Command Line to configure",1)
                while True:
                    input("Restart this PM2 once you have logged in again. Press Enter to continue...")

            input_field.send_keys(seed_phrase)
            self.output(f"Bước {self.step} -Đã nhập thành công cụm từ hạt giống...", 3)
            self.increase_step()

            #Nhấp vào nút tiếp tục sau khi nhập cụm từ hạt giống:
            xpath = "//button[not(@disabled)]//span[contains(text(), 'Continue')]"
            self.move_and_click(xpath, 30, True, "click continue after seedphrase entry", self.step, "clickable")
            self.increase_step()
        else:
            self.output("Seed phrase textarea not found within the timeout period.", 2)
    
    def next_steps(self):
        self.driver = self.get_driver()
        self.driver.get("https://www.treemine.app/login")
        if self.step:
            pass
        else:
            self.step = "01"

        self.check_login()

        if not (self.forceRequestUserAgent or self.settings["requestUserAgent"]):
            cookies_path = f"{self.session_path}/cookies.json"
            cookies = self.driver.get_cookies()
            with open(cookies_path, 'w') as file:
                json.dump(cookies, file)
        else:
            user_agent = self.prompt_user_agent()
            cookies_path = f"{self.session_path}/cookies.json"
            cookies = self.driver.get_cookies()
            cookies.append({"name": "user_agent", "value": user_agent})  #Lưu tác nhân người dùng vào cookie
            with open(cookies_path, 'w') as file:
                json.dump(cookies, file)

    def find_working_link(self,old_step):
        self.output(f"Step {self.step} - Attempting to open a link Following Twitter...",2)

        start_app_xpath = "//p[contains(text(), '& Tag')]"

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
                self.output(f"Step {self.step} - None of the 'Follow on Twitter' buttons were clickable.\n",1)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-no-clickable-button.png"
                    self.driver.save_screenshot(screenshot_path)
                return False
            else:
                self.output(f"Step {self.step} - Successfully able to open a link to Follow on Twitter..\n",3)
                if self.settings['debugIsOn']:
                    screenshot_path = f"{self.screenshots_path}/{self.step}-app-opened.png"
                    self.driver.save_screenshot(screenshot_path)
                return True

        except TimeoutException:
            self.output(f"Step {self.step} - Failed to find the 'Follow on Twitter' button within the expected timeframe.\n",1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-timeout-finding-button.png"
                self.driver.save_screenshot(screenshot_path)
            return False
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi khi cố gắng Follow on Twitter: {e}\n",1)
            if self.settings['debugIsOn']:
                screenshot_path = f"{self.screenshots_path}/{self.step}-unexpected-error-following-twitter.png"
                self.driver.save_screenshot(screenshot_path)
            return False

    def full_claim(self):
        self.driver = self.get_driver()
        
        self.step = "100"
        
        def get_seed_phrase(screenshots_path):
            seed_file_path = os.path.join(self.screenshots_path, 'seed.txt')
            if os.path.exists(seed_file_path):
                with open(seed_file_path, 'r') as file:
                    seed_phrase = file.read().strip()
                return seed_phrase
            else:
                return None
        
        self.driver.get("https://www.treemine.app/missions")
        
        self.check_login()
        self.increase_step()

        self.driver.get("https://www.treemine.app/missions")

        xpath = "//button[contains(text(), 'AXE')]"
        self.move_and_click(xpath, 30, True, "click the AXE button", self.step, "clickable")
        self.increase_step()

        def extract_minutes_from_string(text):
            match = re.search(r'(\d+)', text)
            if match:
                return int(match.group(1))
            return None

        xpath = "//span[contains(., 'minutes after')]"
        axe_time = self.move_and_click(xpath, 5, False, "check the axe time", self.step, "visible")
        if axe_time:
            minutes = extract_minutes_from_string(axe_time.text)
            if minutes is not None:
                self.output(f"Step {self.step} - The axe can not be claimed for another {minutes} minutes.", 2)
        else:
            self.find_working_link(self.step)
        self.increase_step()

        self.driver.get("https://www.treemine.app/miner")
        self.get_balance(False)
        self.increase_step()

        wait_time_text = self.get_wait_time(self.step, "pre-claim") 

        if wait_time_text != self.pot_full:
            matches = re.findall(r'(\d+)([hm])', wait_time_text)
            remaining_wait_time = (sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)) + self.random_offset
            if remaining_wait_time < 5 or self.settings["forceClaim"]:
                self.settings['forceClaim'] = True
                self.output(f"Bước {self.step} -thời gian còn lại để yêu cầu ít hơn thời gian bù đắp ngẫu nhiên nên việc áp dụng: settings['forceClaim'] = True", 3)
            else:
                if remaining_wait_time > 90:
                    self.output(f"Step {self.step} - Initial wait time returned as {remaining_wait_time}.",3)
                    self.increase_step()
                    remaining_wait_time = 90
                    self.random_offset = 0
                    wait_time_text = "1h30m"
                    self.output(f"Step {self.step} - As there are no gas fees with Tree coin - claim forced to 90 minutes.",3)
                    self.increase_step()
                self.output(f"TÌNH TRẠNG: Xem xét {wait_time_text}, chúng tôi sẽ quay lại ngủ trong {remaining_wait_time} phút.", 1)
                return remaining_wait_time

        if wait_time_text == "không xác định":
            return 15

        try:
            self.output(f"Bước {self.step} -Thời gian chờ yêu cầu trước là: {wait_time_text} và thời gian bù trừ ngẫu nhiên là {self.random_offset} phút.",1)
            self.increase_step()

            if wait_time_text == self.pot_full or self.settings['forceClaim']:
                try:
                    original_window = self.driver.current_window_handle
                    xpath = "//button[contains(text(), 'Check NEWS')]"
                    self.move_and_click(xpath, 3, True, "kiểm tra TIN TỨC.", self.step, "clickable")
                    self.driver.switch_to.window(original_window)
                except TimeoutException:
                    if self.settings['debugIsOn']:
                        self.output(f"Bước {self.step} -Không có tin tức nào để kiểm tra hoặc không tìm thấy nút.",3)
                self.increase_step()

                try:
                    #Bấm vào nút "Yêu cầu HOT":
                    xpath = "//button[contains(text(), 'Claim')]"
                    self.move_and_click(xpath, 30, True, "click the claim button", self.step, "clickable")
                    self.increase_step()

                    #Bây giờ chúng ta hãy thử lại để có được thời gian còn lại cho đến khi đầy.
#Ngày 24 tháng 4 -Hãy đợi vòng quay biến mất trước khi cố gắng lấp đầy thời gian mới.
                    self.output(f"Bước {self.step} -Đợi Claim spinner đang chờ xử lý ...",2)
                    time.sleep(5)
                    wait = WebDriverWait(self.driver, 240)
                    spinner_xpath = "//*[contains(@class, 'spinner')]" 
                    try:
                        wait.until(EC.invisibility_of_element_located((By.XPATH, spinner_xpath)))
                        self.output(f"Bước {self.step} -Vòng quay hành động đang chờ xử lý đã dừng.\n",3)
                    except TimeoutException:
                        self.output(f"Bước {self.step} -Có vẻ như trang web bị lag -Spinner không biến mất kịp thời.\n",2)
                    self.increase_step()
                    wait_time_text = self.get_wait_time(self.step, "post-claim") 
                    matches = re.findall(r'(\d+)([hm])', wait_time_text)
                    total_wait_time = self.apply_random_offset(sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches))
                    self.increase_step()

                    if total_wait_time > 90:
                        total_wait_time = 90
                        self.output(f"Step {self.step} - As there are no gas fees with Tree coin - claim forced to 90 minutes.",2)
                        self.increase_step()

                    self.get_balance(True)

                    if wait_time_text == "0h 0m to fill":
                        self.output(f"STATUS: The wait timer is still showing: Filled - possible issue with Axe's not claiming.",1)
                        self.output(f"Bước {self.step} -Điều này có nghĩa là xác nhận quyền sở hữu không thành công hoặc có độ trễ >4 phút trong trò chơi.",1)
                        self.output(f"Bước {self.step} -Chúng tôi sẽ kiểm tra lại sau 1 giờ để xem khiếu nại đã được xử lý chưa và nếu chưa hãy thử lại.",2)
                    else:
                        self.output(f"TRẠNG THÁI: Xác nhận quyền sở hữu thành công: Yêu cầu tiếp theo {wait_time_text} /{total_wait_time} phút.",1)
                    return max(60, total_wait_time)

                except TimeoutException:
                    self.output(f"TRẠNG THÁI: Quá trình xác nhận quyền sở hữu đã hết thời gian: Có thể trang web bị lag? Sẽ thử lại sau một giờ.",1)
                    return 60
                except Exception as e:
                    self.output(f"TRẠNG THÁI: Đã xảy ra lỗi khi cố gắng xác nhận quyền sở hữu: {e}\nHãy đợi một giờ và thử lại",1)
                    return 60

            else:
                #Nếu ví chưa sẵn sàng để nhận, hãy tính thời gian chờ dựa trên bộ đếm thời gian được cung cấp trên trang
                matches = re.findall(r'(\d+)([hm])', wait_time_text)
                if matches:
                    total_time = sum(int(value) * (60 if unit == 'h' else 1) for value, unit in matches)
                    total_time += 1
                    total_time = max(5, total_time) #Đợi ít nhất 5 phút hoặc thời gian
                    self.output(f"Bước {self.step} -Chưa đến lúc nhận ví này. Đợi {total_time} phút cho đến khi bộ nhớ đầy.",2)
                    return total_time 
                else:
                    self.output(f"Bước {self.step} -Không tìm thấy dữ liệu về thời gian chờ? Hãy kiểm tra lại sau một giờ nữa.",2)
                    return 60  #Thời gian chờ mặc định khi không tìm thấy thời gian cụ thể cho đến khi được lấp đầy.
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi không mong muốn: {e}",1)
            return 60  #Thời gian chờ mặc định trong trường hợp xảy ra lỗi không mong muốn
            
    def get_balance(self, claimed=False):
        global step
        prefix = "After" if claimed else "Before"
        default_priority = 2 if claimed else 3

        #Tự động điều chỉnh mức độ ưu tiên của nhật ký
        priority = max(self.settings['verboseLevel'], default_priority)

        #Xây dựng số dư cụ thể XPath
        balance_text = f'{prefix} BALANCE:' if claimed else f'{prefix} BALANCE:'
        balance_xpath = "//span[contains(text(), 'TREE Balance:')]/following-sibling::span[1]"

        try:
            #Đợi phần tử hiển thị dựa trên XPath
            element = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, balance_xpath))
            )

            #Kiểm tra xem phần tử có phải là Không và xử lý số dư
            if element:
                balance_part = element.text.strip()
                self.output(f"Step {self.step} - {balance_text} {balance_part}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
#Xây dựng số dư cụ thể XPath
        profit_text = f'{prefix} PROFIT/HOUR:'
        profit_xpath = "//p[contains(text(), 'TREE/hour')]//span"

        try:
            #Đợi phần tử hiển thị dựa trên XPath
            element = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, profit_xpath))
            )

            #Kiểm tra xem phần tử có phải là Không và xử lý số dư
            if element:
                profit_part = element.text.strip()
                self.output(f"Bước {self.step} - {profit_text} {profit_part}", priority)

        except NoSuchElementException:
            self.output(f"Bước {self.step} -Không tìm thấy phần tử chứa '{prefix} Số dư:'.", priority)
        except Exception as e:
            self.output(f"Bước {self.step} -Đã xảy ra lỗi: {str(e)}", priority)  #Cung cấp lỗi dưới dạng chuỗi để ghi nhật ký
#Hàm bước tăng dần, giả sử để xử lý logic bước tiếp theo
        self.increase_step()

    def get_wait_time(self, step_number="108", beforeAfter = "pre-claim", max_attempts=2):
    
        for attempt in range(1, max_attempts + 1):
            try:
                xpath = f"//div[contains(., 'Storage')]//p[contains(., '{self.pot_full}') or contains(., '{self.pot_filling}')]"
                wait_time_element = self.move_and_click(xpath, 20, True, f"get the {beforeAfter} wait timer", self.step, "visible")
                #Kiểm tra xem Wait_time_element có phải là Không
                if wait_time_element is not None:
                    return wait_time_element.text
                else:
                    self.output(f"Bước {self.step} -Cố gắng {attempt}: Không tìm thấy phần tử thời gian chờ. Clicking the 'Storage' link and retrying...",3)
                    storage_xpath = "//h4[text()='Storage']"
                    self.move_and_click(storage_xpath, 30, True, "click the 'storage' link", f"{self.step} recheck", "clickable")
                    self.output(f"Step {self.step} - Attempted to select strorage again...",3)
                return wait_time_element.text

            except TimeoutException:
                if attempt < max_attempts:  #Đã thử không thành công nhưng vẫn thử lại
                    self.output(f"Bước {self.step} -Cố gắng {attempt}: Không tìm thấy phần tử thời gian chờ. Clicking the 'Storage' link and retrying...",3)
                    storage_xpath = "//h4[text()='Storage']"
                    self.move_and_click(storage_xpath, 30, True, "click the 'storage' link", f"{self.step} recheck", "clickable")
                else:  #Không còn lần thử lại nào sau lần thất bại đầu tiên
                    self.output(f"Bước {self.step} -Cố gắng {attempt}: Không tìm thấy phần tử thời gian chờ.",3)

            except Exception as e:
                self.output(f"Bước {self.step} -Đã xảy ra lỗi khi thử {attempt}: {e}",3)

        #Nếu mọi nỗ lực đều thất bại
        return "không xác định"


def main():
    claimer = TreeClaimer()
    claimer.run()


if __name__ == "__main__":
    main()
