# -*- coding: utf-8 -*-
from selenium import webdriver
import time
import argparse
import re
import json
from gearman import GearmanWorker

parser = argparse.ArgumentParser()
parser.add_argument('--debug', help='enable debug mode', action="store_true")
parser.add_argument('--chrome', help='using Chrome webdriver instead of PhantomJS', action="store_true")
parser.add_argument('--gearman_host', help='provide gearman host', required=True)
args = parser.parse_args()
debug = args.debug
chrome = args.chrome

class browser:
    """docstring for browser."""

    def __init__(self, debug = False, chrome = False ):
        if chrome:
            self.chrome = chrome
            self.browser = webdriver.Chrome()
        else:
            self.browser = webdriver.PhantomJS()
            self.browser.command_executor._commands['executePhantomScript'] = ('POST', '/session/$sessionId/phantom/execute')
            self.resourceRequestedLogic()
        self.debug = debug


    def clearDriverCache(self):
        self.browser.execute('executePhantomScript', {'script': '''
            var page = this;
            page.clearMemoryCache();
        ''', 'args': []})

    def resourceRequestedLogic(self):
        self.browser.execute('executePhantomScript', {'script': '''
            var page = this;
            page.onResourceRequested = function(request, networkRequest) {
                if (/\.(jpg|jpeg|png|mp3)/i.test(request.url))
                {
                    //console.log('Final with css! Suppressing image: ' + request.url);
                    networkRequest.abort();
                    return;
                }
            }
        ''', 'args': []})

    def auth(self, credencials):
        br = self.browser
        br.get("https://my.mail.ru/")
        self.log(u'Open ' +br.current_url)
        login = br.find_element_by_class_name("l-loginform_row_label_input")
        login.clear()
        self.log(u'Login fill')
        login.send_keys(credencials['login'])
        password = br.find_element_by_css_selector("form.l-loginform input[type=password]")
        password.clear()
        self.log(u'Password fill')
        password.send_keys(credencials['password'])
        submit = br.find_element_by_css_selector("form.l-loginform")
        self.log(u'Form submit')
        submit.submit()

    def getUsersFriends(self, peopleArr):
        returnEmails = []
        for user in peopleArr:
            email = user['email']
            m = re.match(r"^(.*)@(.*)\..*", email)
            userLink = 'https://my.mail.ru/{}/{}/friends'.format(m.group(2), m.group(1))
            self.log(u'Getting friends of user ' + email + ' [' + userLink + ']')
            tmpRes = self.getFriends(userLink)
            returnEmails = returnEmails + tmpRes
        return returnEmails

    def getFriends(self, userLink):
        br = self.browser
        br.get(userLink)

        # Get scroll height
        last_height = br.execute_script("return document.body.scrollHeight")

        while True:
            # Scroll down to bottom
            br.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Wait to load page
            time.sleep(2)
            # Calculate new scroll height and compare with last scroll height
            new_height = br.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            # print 'Scrolling to bottom completed'

        friends = br.find_element_by_class_name("b-catalog__friends-items").find_elements_by_tag_name('ul')
        emails = []
        for el in friends:
            emails.append(el.get_attribute('data-email'))
        self.log('\tGet {} emails.'.format(len(friends)))
        if not self.chrome:
            self.clearDriverCache()
        return emails

    def getUrl(self, url):
        self.browser.get(url)
        # print u'Открыта страница ' + self.browser.title

    def closeAll(self):
        self.browser.close()
        self.browser.quit()
        self.log(u'Browser process was ended')
        self.log(u'')

    def log(self, text):
        if self.debug:
            print(text)


def parseFriends(worker, job):
    jobArr = json.loads(job.data)
    br = browser(debug, chrome)
    br.auth(jobArr['auth'])
    jobResult = br.getUsersFriends(jobArr['users'])
    br.closeAll()
    return json.dumps(jobResult)

worker = GearmanWorker([args.gearman_host])
worker.register_task('parseFriends', parseFriends)
worker.work()
