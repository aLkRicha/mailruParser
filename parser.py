# -*- coding: utf-8 -*-
from selenium import webdriver

from gearman import GearmanWorker
import time
import argparse
import re
import json
import pickle
import pprint
import datetime
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import os

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('--debug', help='enable debug mode', action="store_true")
parser.add_argument('--chrome', help='using Chrome webdriver instead of PhantomJS', action="store_true")
parser.add_argument('--gearman_host', help='provide gearman host', required=True)
args = parser.parse_args()
debug = args.debug
chrome = args.chrome


class Browser:
    """docstring for browser."""
    main_tab = None
    new_tab = None

    def __init__(self, debug=False, chrome=False):
        self.chrome = chrome
        self.debug = debug
        self.open_window()

    def open_window(self):
        if self.chrome:
            chrome_options = Options()
            # chrome_options.add_argument("headless")
            self.browser = webdriver.Chrome(chrome_options=chrome_options)
        else:
            self.browser = webdriver.PhantomJS(service_args=['--disk-cache=true','--load-images=true'])
            self.browser.command_executor._commands['executePhantomScript'] = (
            'POST', '/session/$sessionId/phantom/execute')
            self.resourceRequestedLogic()

    def clearDriverCache(self):
        self.browser.execute('executePhantomScript', {'script': '''
            var page = this;
            page.clearMemoryCache();
        ''', 'args': []})

    def resourceRequestedLogic(self):
        self.browser.execute('executePhantomScript', {'script': '''
            var page = this;
            page.onResourceRequested = function(request, networkRequest) {
                if (/.*(avatar|pic|gif|png|mp3)/i.test(request.url))
                {
                    //console.log('Final with css! Suppressing image: ' + request.url);
                    networkRequest.abort();
                    return;
                }
            }
        ''', 'args': []})

    def auth(self, credencials):
        br = self.browser
        m = re.match(r"^(.*)@.*", credencials['login'])
        cookie_name = m.group(1)
        br.get("https://my.mail.ru/")
        self.log(u'Open ' + br.current_url)
        # try:
        #     self.log('try to auth with cookies')
        #     cookies = pickle.load(open('var/cookies/{}.pkl'.format(cookie_name), "rb"))
        #     for cookie in cookies:
        #         br.add_cookie(cookie)
        #     br.refresh()
        #     br.find_element_by_css_selector('.b-left-menu__avatar')
        # except:
        self.log('Authentication')
        login = br.find_element_by_class_name("l-loginform_row_label_input")
        login.clear()
        self.log('---> Login fill')
        login.send_keys(credencials['login'])
        password = br.find_element_by_css_selector("form.l-loginform input[type=password]")
        password.clear()
        self.log('---> Password fill')
        password.send_keys(credencials['password'])
        submit = br.find_element_by_css_selector("form.l-loginform")
        self.log('---> Form submit')
        submit.submit()
        pickle.dump(br.get_cookies(), open('var/cookies/{}.pkl'.format(cookie_name), "wb"))
        self.log('---> Authentication complete')
        time.sleep(1.5)
        # self.main_tab = br.current_window_handle

    def getUsersFriends(self, peopleArr):
        returnEmails = {}
        for user in peopleArr:
            email = user['email']
            m = re.match(r"^(.*)@(.*)\..*", email)
            userLink = 'https://my.mail.ru/{}/{}/friends'.format(m.group(2), m.group(1))
            self.get_user(email)
            tmpRes = self.get_friends()
            returnEmails[email] = tmpRes
            self.browser.execute_script("window.open('https://my.mail.ru/')")
            self.browser.close()
            self.browser.switch_to.window(self.browser.window_handles[0])
        self.clearDriverCache()
        return returnEmails

    def get_user(self, email):
        br = self.browser
        br.get('https://my.mail.ru')
        self.log('Start searching {}'.format(email))
        self.browser.save_screenshot('var/1.png')
        search_input = br.find_element_by_css_selector('.b-head__menu__search__input')
        search_input.clear()
        search_button = br.find_element_by_css_selector('.b-head__menu__search__button')
        ActionChains(br).move_to_element(search_input).perform()
        search_input.send_keys(email)
        ActionChains(br).move_to_element(search_button).click().perform()
        # time.sleep(3)
        user_link = self.wait_for(By.CSS_SELECTOR, '.b-search__users__item__field')
        ActionChains(br).move_to_element(user_link).perform()
        href = user_link.get_attribute('href')
        self.log('Moving to {}'.format(href))
        br.get(href)
        time.sleep(3)
        # print(br.window_handles)
        # print('before switch {}'.format(br.current_window_handle))
        # self.new_tab = br.window_handles[1]
        # br.switch_to.window(self.new_tab)
        # print('after switch {}'.format(br.current_window_handle))

    def get_friends(self):
        br = self.browser
        self.log('Moving to user friends list')
        friends_link = self.wait_for(By.CSS_SELECTOR, '.profile__menu a:nth-child(2)')
        ActionChains(br).move_to_element(friends_link).perform()
        friends_link.click()
        # br.execute_script("arguments[0].click();", friends_link)
        time.sleep(2)

        self.log('Start scrolling friends list')
        # Get scroll height
        last_height = br.execute_script("return document.body.scrollHeight")

        while True:
            footer = br.find_element_by_css_selector('.b-footer')
            # print(footer)
            # ActionChains(br).move_to_element(footer).perform()
            # Scroll down to bottom
            br.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Wait to load page
            time.sleep(2)
            # Calculate new scroll height and compare with last scroll height
            new_height = br.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        self.log('---> Scrolling complete')
        friends = br.find_element_by_class_name("b-catalog__friends-items").find_elements_by_tag_name('ul')
        emails = []
        self.log('Parsing emails')
        for el in friends:
            emails.append(el.get_attribute('data-email'))
        # if not self.chrome:
        #     self.clearDriverCache()

        # br.close()
        # print('before switch to main')
        # br.switch_to.window(self.main_tab)
        # print('after switch to main')
        return emails

    def getUrl(self, url):
        self.browser.get(url)
        # print u'Открыта страница ' + self.browser.title

    def close_all(self):
        self.browser.save_screenshot('var/exit.png')
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


def parseFriends(worker, job):
    jobArr = json.loads(job.data)
    br = Browser(debug, chrome)
    br.auth(jobArr['auth'])
    jobResult = br.getUsersFriends(jobArr['users'])
    br.close_all()
    return json.dumps(jobResult)

worker = GearmanWorker([args.gearman_host])
worker.register_task('parseFriends', parseFriends)
worker.work()
