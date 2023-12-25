import time

from selenium import webdriver
import selenium
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from simphile import jaccard_similarity, euclidian_similarity, compression_similarity

import os


class Driver:
    def __init__(self,session):
        options = selenium.webdriver.ChromeOptions()
        chrome_dir = os.getcwd()
        options.add_argument(f'--user-data-dir={chrome_dir}/Files/chrome_sessions/{session}')
        self.driver = webdriver.Chrome(service=Service(executable_path=r'Files\chromedriver.exe'),
                                    options=options,)

    def get_elem_by_path(self,x_path,index=0,m_elem=None):
        if m_elem:
            elems = m_elem.find_elements(By.XPATH, x_path)
        else:
            elems = self.driver.find_elements(By.XPATH,x_path)
        if index == 'all':
            return elems
        if len(elems) > index:
            return elems[index]

class TelegramSelenium:
    def __init__(self,phone):
        self.session = Driver(phone)
        self.phone = phone
        self.session.driver.get('https://web.telegram.org/a/')

    def login(self):
        try:
            self.session.driver.get('https://web.telegram.org/a/')
            time.sleep(10)
            self.session.get_elem_by_path('//*[@class="Button default primary text"]').click()
            elem = self.session.get_elem_by_path('//*[@id="sign-in-phone-number"]')
            elem.clear()
            elem.send_keys(self.phone)
            self.session.get_elem_by_path('//*[@class="ripple-container"]').click()
            code = input('Please get validation code:\n')
            self.session.get_elem_by_path('//*[@id="sign-in-code"]').send_keys(code)
        except Exception as e:
            print(str(e))

    def send_message(self, user, message, type_='id', index=0):
        try:
            if type_ == 'id':
                self.session.driver.get(f'https://web.telegram.org/a/#{user}')
            else:
                self.session.get_elem_by_path('//*[@id="telegram-search-input"]').send_keys(user)
                time.sleep(5)
                chats = self.session.get_elem_by_path('//*[@class="ListItem chat-item-clickable search-result"]','all')
                selected_chat = None
                similarity = 0
                if type_ == "code":
                    for chat in chats:
                        elem = self.session.get_elem_by_path('.//*[@class="status"]//*[@class="handle"]', 0, chat)
                        if elem and elem.text == user:
                            selected_chat = elem
                            break
                else:
                    for chat in chats:
                        elem = self.session.get_elem_by_path('.//*[contains(@class,"fullName")')
                        if elem:
                            m_similarity = compression_similarity(elem.text,user)
                            if m_similarity > similarity:
                                similarity = m_similarity
                                selected_chat = chat
                if selected_chat:
                    selected_chat.click()
            time.sleep(1)
            self.session.get_elem_by_path('//*[@id="editable-message-text"]').send_keys(message)
            self.session.get_elem_by_path('//*[@class="Button send main-button default secondary round click-allowed"]').click()
            print('s')
        except Exception as e:
            print(str(e))


def run():
    telegram = TelegramSelenium('989368468323')
    while True:
        telegram.send_message(input("get user: "), "salam", "code")


if __name__ == '__main__':
    run()

