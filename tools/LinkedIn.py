import os
import time
import google_sheet
import selenium.webdriver
from selenium.webdriver.common.by import By
search_link = "https://www.linkedin.com/search/results/people/?geoUrn=%5B%22103644278%22%5D&industry=%5B%221532%22%2C%2287%22%2C%2295%22%2C%22116%22%2C%2292%22%5D&origin=FACETED_SEARCH&sid=2!S"# &keywords=system%20analyst


class LinkedIn():
    def __init__(self, name='default'):
        self.name = name
        dir_path = os.getcwd()
        profile = os.path.join(dir_path, f"Files/User_Data/{name}")
        options = selenium.webdriver.ChromeOptions()
        options.add_argument(
            r"user-data-dir={}".format(profile))
        self.driver = selenium.webdriver.Chrome(executable_path="Files/chromedriver.exe",
                                                service_log_path="Files/chromelog.txt", options=options)

    def search(self, link=search_link):
        self.driver.get(link)
        time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        contacts = self.get_all_members_in_page()
        elems = self.driver.find_elements(By.XPATH, '//*[@aria-label="Next"]')
        k = 0
        while elems and not elems[0].get_property('disabled') and k < 10000:
            elems[0].click()
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            contacts.extend(self.get_all_members_in_page())
            elems = self.driver.find_elements(By.XPATH, '//*[@aria-label="Next"]')
            k += 1
        return contacts

    def get_all_members_in_page(self):
        items = self.driver.find_elements(By.XPATH,
                                          '//*[@class="reusable-search__result-container"]//*[@class="entity-result__item"]')
        contacts = []
        for item in items:
            try:
                elems = item.find_elements(By.XPATH, './/*[@class="entity-result__universal-image"]//img')
                img = elems[0].get_property('src') if elems else None
                elems = item.find_elements(By.XPATH, './/*[@class="app-aware-link "]')
                link = elems[0].get_property('href') if elems else ""
                #link0 = link
                link = link if not link.__contains__('search/results') else None
                name = elems[0].text if link else None
                elems = item.find_elements(By.XPATH, './/*[@class="entity-result__primary-subtitle t-14 t-black t-normal"]')
                line1 = elems[0].text if elems else None
                elems = item.find_elements(By.XPATH, './/*[@class="entity-result__secondary-subtitle t-14 t-normal"]')
                line2 = elems[0].text if elems else None
                elems = item.find_elements(By.XPATH, './*/*[contains(@class,"linked-area flex-1")]')
                line3 = elems[0].text if elems else None
                connect = item.find_elements(By.XPATH, './/*[contains(@aria-label,"to connect")]')
                pending = item.find_elements(By.XPATH, './/*[contains(@aria-label,"Pending")]')
                message = item.find_elements(By.XPATH, './/*[contains(@aria-label,"Message")]')
                follow = item.find_elements(By.XPATH, './/*[contains(@aria-label,"Follow")]')
                status = "connect" if connect else "follow" if follow else "pending" if pending else "message" if message else None
                contacts.append({
                    "image": img,
                    "link": link,
                    "name": name,
                    "line1": line1,
                    "line2": line2,
                    "line3": line3,
                    "status": status,
                    #"link0": link0
                })
            except Exception as e:
                print(str(e))
        return contacts


if __name__ == "__main__":
    gsheet = google_sheet.GSheet("1VuJU-0sBiKYOHHp5qwxwaDJVLVAXhNAp9Q8LkijTTfM")
    w = LinkedIn("Main-User")
    contacts = w.search()
    gsheet.update_rows("search",contacts,"new",expandColumns='yes')
    print('')
