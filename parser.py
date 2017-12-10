# -*- coding: utf-8 -*-
import argparse
import datetime
import json
import os
import pickle
import time
import sys

from gearman import GearmanWorker
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('--debug', help='enable debug mode', action="store_true")
parser.add_argument('--head', help='using chrome driver in non-headless mode', action="store_true")
parser.add_argument('--gearman_host', help='provide gearman host', required=True)
args = parser.parse_args()
debug = args.debug
head = args.head


class Browser:
    """docstring for browser."""
    credentials = None
    browser = None

    def __init__(self, debug=False, head=False):
        self.head = head
        self.debug = debug
        print(1)
        self.open_window()

    def open_window(self):
        print(2)
        options = webdriver.ChromeOptions()
        print(3)
        if not self.head:
            options.add_argument('headless')
            options.add_argument('no-sandbox')
            options.add_argument("disable-gpu")
        try:
            self.browser = webdriver.Chrome(chrome_options=options)
        except WebDriverException as err:
            print(err.msg)
            print(err.message)
            raise
        print(5)

    def auth(self, credentials):
        br = self.browser
        self.credentials = credentials
        try:
            self.log('Authentication with cookies:')
            self.load_auth_cookies()
            br.find_element_by_css_selector('.b-left-menu__avatar')
            self.log('---> Success')
        except:
            self.log('---> Failed')
            self.log('Authentication with email/password')
            br.get('https://my.mail.ru')
            login = br.find_element_by_class_name("l-loginform_row_label_input")
            login.clear()
            self.log('---> Login fill')
            login.send_keys(self.credentials['login'])
            password = br.find_element_by_css_selector("form.l-loginform input[type=password]")
            password.clear()
            self.log('---> Password fill')
            password.send_keys(self.credentials['password'])
            submit = br.find_element_by_css_selector("form.l-loginform")
            self.log('---> Form submit')
            submit.submit()
            self.dump_auth_cookies()
            self.log('---> Authentication complete')
        time.sleep(1.5)

    def dump_auth_cookies(self):
        br = self.browser
        br.get('https://my.mail.ru')
        self.log('---> Saving cookies for my.mail.ru')
        pickle.dump(br.get_cookies(), open('var/cookies/my._{}.pkl'.format(self.credentials['login']), "wb"))
        br.get('https://auth.mail.ru')
        self.log('---> Saving cookies for auth.mail.ru')
        pickle.dump(br.get_cookies(), open('var/cookies/auth._{}.pkl'.format(self.credentials['login']), "wb"))

    def load_auth_cookies(self):
        br = self.browser
        br.get('https://auth.mail.ru')
        cookies = pickle.load(open('var/cookies/auth._{}.pkl'.format(self.credentials['login']), "rb"))
        for cookie in cookies:
            br.add_cookie(cookie)
        self.log('---> Loading cookies for auth.mail.ru')
        br.get('https://my.mail.ru')
        cookies = pickle.load(open('var/cookies/my._{}.pkl'.format(self.credentials['login']), "rb"))
        for cookie in cookies:
            br.add_cookie(cookie)
        self.log('---> Loading cookies for my.mail.ru')
        br.refresh()

    def get_users_friends(self, peopleArr):
        return_emails = {}
        for user in peopleArr:
            email = user['email']
            self.get_user(email)
            tmp_res = self.get_friends()
            return_emails[email] = tmp_res
        return return_emails

    def get_user(self, email):
        br = self.browser
        br.get('https://my.mail.ru')
        self.log('Start searching {}'.format(email))
        search_input = br.find_element_by_css_selector('.b-head__menu__search__input')
        search_input.clear()
        search_button = br.find_element_by_css_selector('.b-head__menu__search__button')
        ActionChains(br).move_to_element(search_input).perform()
        search_input.send_keys(email)
        ActionChains(br).move_to_element(search_button).click().perform()
        user_link = self.wait_for(By.CSS_SELECTOR, '.b-search__users__item__field')
        ActionChains(br).move_to_element(user_link).perform()
        href = user_link.get_attribute('href')
        self.log('Moving to {}'.format(href))
        br.get(href)
        time.sleep(3)

    def get_friends(self):
        br = self.browser
        self.log('Moving to user friends list')
        friends_link = self.wait_for(By.CSS_SELECTOR, '.profile__menu a:nth-child(2)')
        ActionChains(br).move_to_element(friends_link).perform()
        friends_link.click()
        time.sleep(2)
        self.log('---> Start scrolling friends list')
        last_height = br.execute_script("return document.body.scrollHeight")
        while True:
            br.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = br.execute_script("return document.body.scrollHeight;")
            if new_height == last_height:
                break
            last_height = new_height
        self.log('---> Scrolling complete')
        friends = br.find_element_by_class_name("b-catalog__friends-items").find_elements_by_tag_name('ul')
        emails = []
        self.log('---> Parsing emails')
        for el in friends:
            emails.append(el.get_attribute('data-email'))
        return emails

    def close_all(self):
        self.browser.close()
        self.browser.quit()
        self.log(u'Browser process was ended')
        self.log(u'')

    def wait_for(self, by, el):
        element = WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((by, el)))
        return element

    def log(self, text):
        if self.debug:
            log_date = datetime.datetime.now()
            formatted_date = log_date.__format__("%d-%m-%Y %H:%M:%S")
            print("[{}] {}".format(formatted_date, text))


def parse_friends(worker, job):
    job_arr = json.loads(job.data)
    br = Browser(debug, head)
    br.auth(job_arr['auth'])
    job_result = br.get_users_friends(job_arr['users'])
    br.close_all()
    return json.dumps(job_result)


worker = GearmanWorker([args.gearman_host])
worker.register_task('parseFriends', parse_friends)
worker.work()
