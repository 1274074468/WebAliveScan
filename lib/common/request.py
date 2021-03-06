from gevent import monkey, pool; monkey.patch_all()
from lib.utils.FileUtils import *
from lib.utils.tools import *
import config
import chardet
import time
import random
import urllib3
import requests
import csv
from bs4 import BeautifulSoup
urllib3.disable_warnings()


class Request:
    def __init__(self, target, port, output):
        self.output = output
        self.url_list = self.gen_url_list(target, port)
        self.total = len(self.url_list)
        self.output.config(config.threads, self.total)
        self.output.target(target)
        self.index = 0
        self.alive_web = []
        self.alive_path = config.result_save_path.joinpath('%s_alive_results.csv' % str(time.time()).split('.')[0])
        self.brute_path = config.result_save_path.joinpath('%s_brute_results.csv' % str(time.time()).split('.')[0])
        self.alive_result_list = []
        self.main()

    def gen_url_by_port(self, domain, port):
        protocols = ['http://', 'https://']
        if port == 80:
            url = f'http://{domain}'
            return url
        elif port == 443:
            url = f'https://{domain}'
            return url
        else:
            for protocol in protocols:
                url = f'{protocol}{domain}:{port}'
                return url

    def gen_url_list(self, target, port):
        try:
            # 获取文件内容
            domain_list = open(target, 'r').readlines()

            # 获取端口
            ports = set()
            if isinstance(port, set):
                ports = port
            elif isinstance(port, list):
                ports = set(port)
            elif isinstance(port, tuple):
                ports = set(port)
            elif isinstance(port, int):
                if 0 <= port <= 65535:
                    ports = {port}
            elif port in {'default', 'small', 'medium', 'large'}:
                ports = config.ports.get(port)
            if not ports:  # 意外情况
                ports = {80}

            # 生成URL
            url_list = []
            for domain in domain_list:
                domain = domain.strip()
                if ':' in domain:
                    domain, port = domain.split(':')
                    url_list.append(self.gen_url_by_port(domain, int(port)))
                    continue
                for port in ports:
                    url_list.append(self.gen_url_by_port(domain, port))
            return url_list
        except FileNotFoundError as e:
            self.output.debug(e)
            exit()

    def request(self, url):
        try:
            r = requests.get(url, timeout=config.timeout, headers=self.get_headers(), verify=config.verify_ssl,
                             allow_redirects=config.allow_redirects)
            text = r.content.decode(encoding=chardet.detect(r.content)['encoding'])
            title = self.get_title(text).strip().replace('\r', '').replace('\n', '')
            status = r.status_code
            size = FileUtils.sizeHuman(len(r.text))
            if status in config.ignore_status_code:
                raise Exception
            self.output.statusReport(url, status, size, title)
            result = [title, url, str(status), size, '']
            self.alive_web.append(url)
            self.alive_result_list.append(result)
            return r, text
        except Exception as e:
            return e

    def fetch_url(self, url):
        # print(url)
        self.index = self.index + 1
        self.output.lastPath(url,  self.index, self.total)
        return self.request(url)

    def get_headers(self):
        """
        生成伪造请求头
        """
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36',
            'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/68.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:61.0) '
            'Gecko/20100101 Firefox/68.0',
            'Mozilla/5.0 (X11; Linux i586; rv:31.0) Gecko/20100101 Firefox/68.0']
        ua = random.choice(user_agents)
        headers = {
            'Accept': 'text/html,application/xhtml+xml,'
                      'application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Referer': 'https://www.google.com/',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': ua,
        }
        return headers

    def get_title(self, markup):
        """
        获取标题
        :param markup: html标签
        :return: 标题
        """
        soup = BeautifulSoup(markup, 'lxml')

        title = soup.title
        if title:
            return title.text

        h1 = soup.h1
        if h1:
            return h1.text

        h2 = soup.h2
        if h2:
            return h2.text

        h3 = soup.h3
        if h2:
            return h3.text

        desc = soup.find('meta', attrs={'name': 'description'})
        if desc:
            return desc['content']

        word = soup.find('meta', attrs={'name': 'keywords'})
        if word:
            return word['content']

        text = soup.text
        if len(text) <= 200:
            return text
        return ''

    def main(self):
        gevent_pool = pool.Pool(config.threads)
        while self.url_list:
            tasks = [gevent_pool.spawn(self.fetch_url, self.url_list.pop())
                     for i in range(len(self.url_list[:config.threads*10]))]
            for task in tasks:
                task.join()
            del tasks

