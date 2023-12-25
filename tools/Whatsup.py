import os
import pickle
import time

import selenium.webdriver
from selenium.webdriver.common.by import By


class WhatsUpp_messenger():
    def __init__(self, name='default'):
        self.name = name
        dir_path = os.getcwd()
        profile = os.path.join(dir_path, "Files/User_Data", f"wpp/{name}")
        options = selenium.webdriver.ChromeOptions()
        options.add_argument(
            r"user-data-dir={}".format(profile))
        self.driver = selenium.webdriver.Chrome(executable_path="Files/chromedriver.exe", service_log_path="Files/chromelog.txt", options=options)
        self.driver.get("https://web.whatsapp.com/")
        time.sleep(30)

    def send_message(self, to, text, type_='PE'):
        try:
            search_bar = self.driver.find_element(By.XPATH,'//*[@data-testid="chat-list-search"]')
            search_bar.clear()
            search_bar.send_keys(to)
            to_account = self.driver.find_element(By.XPATH, '//*[@class="lhggkp7q ln8gz9je rx9719la"][contains(@style,"translateY(72px)")]')
            to_account.click()
            chat_box = self.driver.find_element(By.XPATH, '//*[@data-testid="conversation-compose-box-input"]')
            chat_box.send_keys(text)
            send_but = self.driver.find_element(By.XPATH, '//*[@data-testid="compose-btn-send"]')
            send_but.click()
            result = 'Sent'
            success = True
        except Exception as e:
            result = str(e)
            success = False
        finally:
            return success, result


if __name__ == "__main__":
    W = WhatsUpp_messenger("09909697140")
    W = WhatsUpp_messenger("09334426627")
    #W = WhatsUpp_messenger("09337674130")
    W = WhatsUpp_messenger("09904573720")
    W = WhatsUpp_messenger("09392061239")
    #W = WhatsUpp_messenger("09337674288")
    W = WhatsUpp_messenger("09392061165")
    W = WhatsUpp_messenger("09388242019")
    W.send_message('+98 912 890 0420','test')

    print('')
