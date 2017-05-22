import json
import logging
import os
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image
from django.db import models
from selenium import webdriver

from .asyncdecorator import Async


class SiteManager(models.Manager):
    def create_Site(self, site_url):
        site = Site()
        site.site_url = site_url
        return site


class Site(models.Model):
    site_url = models.CharField(max_length=100)

    images_json = models.CharField(max_length=9999)

    status = models.CharField(max_length=50, default="(Loading...)")

    available = models.BooleanField(default=True)

    objects = SiteManager()

    def isAvailable(self):
        return self.available

    def getImages(self):
        return json.loads(self.images_json)

    @classmethod
    def create(cls, site_url):
        site = cls(site_url=site_url)
        return site

    def __make_snapshots(self, begin_time, end_time, consistency_mode):

        def is_available(url):
            check_url = 'http://archive.org/wayback/available?url=' + url
            response = str(requests.get(check_url).content)
            return 'available' in response

        def extract_timestamp(item):
            # Here we are extracting timestamp from response
            # Since JSON, provided by archive.com is not valid, we do it manually
            # by splitting response string and selecting correct value from it
            # and replacing quotes then to have a possibility to convert them to numbers
            result = str(item.split(',')[2]).replace('"', '')
            return int(result)

        site_url = self.site_url

        FORMAT = '[%(asctime)-15sl] %(message)s'
        logging.basicConfig(filename='info.log', level=logging.INFO, format=FORMAT)
        logger = logging.getLogger('basic')
        logger.setLevel(logging.INFO)

        timemap_request_url = "http://web.archive.org/web/timemap/json/"
        parsed_uri = urlparse(site_url)

        # If url does not start from http:// or https://, we should add it manually to prevent errors
        if not parsed_uri.scheme:
            site_url = "http://" + site_url
            parsed_uri = urlparse(site_url)
        domain = '{uri.netloc}'.format(uri=parsed_uri)

        # First we must check if site is available in archive.com cache
        # if not -- we just return empty dictionary
        if not is_available(site_url):
            logging.error('{} not available.'.format(site_url))
            self.status = "(Not available)"
            self.images_json = ""
            self.save()
            self.available = False
            return False

        # First slice -- [2:-3] -- is to remove incorrect characters at the beginning: "b'" and "'\n"
        # Second slice -- [1:] -- is to remove first element, which contains only field names,
        # since we don't need it
        logger.info("Getting timemap for '{}'...".format(site_url))
        response_list = str(requests.get(timemap_request_url + site_url).content)[2:-3].split("\\n")[1:]
        logger.info("Timemap received!")

        # Extracting timestamps from response content
        # and filtering them to fit begin_time and end_time
        # if mode == 3
        timestamps = list()
        if consistency_mode == 3:
            timestamps = list(
                filter(lambda x: begin_time <= x <= end_time, list(map(extract_timestamp, response_list))))
            logger.info("Consistency mode: All timestamps: From/To")

        elif consistency_mode == 2:
            timestamps = list(map(extract_timestamp, response_list))
            logger.info("Consistency mode: All available timestamps")

        elif consistency_mode == 1:
            temp_timestamps = list(map(extract_timestamp, response_list))
            logger.info("Consistency mode: One per month")
            timestamps_dict = dict()
            for i in range(0, len(temp_timestamps)):
                key = str(temp_timestamps[i])[4:6]
                timestamps_dict[key] = temp_timestamps[i]

            timestamps = timestamps_dict.values()

        elif consistency_mode == 0:
            logger.info("Consistency mode: One per Year")
            temp_timestamps = list(map(extract_timestamp, response_list))
            timestamps_dict = dict()

            for i in range(0, len(temp_timestamps)):
                key = str(temp_timestamps[i])[0:4]
                timestamps_dict[key] = temp_timestamps[i]

            timestamps = timestamps_dict.values()

        logger.info("Starting browser...")
        driver = webdriver.PhantomJS()
        logger.info("Browser started!")

        # Creating separate directory for site if not exist
        if not os.path.exists('media/' + domain):
            logger.info("Directory 'media/{}' does not exists, creating...".format(domain))
            os.makedirs('media/' + domain)

        file_names = dict()

        max_value = len(timestamps)
        logger.info("Total snapshots: {}".format(max_value))

        for i, timestamp in enumerate(timestamps):
            snapshot_url = "https://web-beta.archive.org/web/{}/{}".format(timestamp, site_url)
            driver.set_window_position(0, 0)
            driver.set_window_size(1024, 768)
            driver.get(snapshot_url)

            # This script adds default background to page, since PhantomJS can do "transparent" snapshot sometimes,
            # and removes archive.com top block from page (last line)
            driver.execute_script("""(function() {
                var style = document.createElement('style'), text = document.createTextNode('body { background: #fff }');
                style.setAttribute('type', 'text/css');
                style.appendChild(text);
                document.head.insertBefore(style, document.head.firstChild);

                /*obj = document.getElementById("wm-ipp");
                if (document.contains(obj) &&
                    obj !== 'null' &&
                    obj !== 'undefined') {
                    obj.remove();
                }*/
            })();""")
            file_name = 'media/{}/snapshot_{}.jpg'.format(domain, timestamp)
            # print("\r{}/{}".format(i, max_value), end='')
            # driver.save_screenshot(file_name)
            screen = driver.get_screenshot_as_png()

            # Crop it back to the window size (it may be taller)
            box = (0, 0, 1024, 768)
            im = Image.open(BytesIO(screen))
            region = im.crop(box)
            region.save(file_name, 'JPEG', optimize=True, quality=95)
            file_names[file_name] = domain
            logger.info("{}/{} snapshots".format(i + 1, max_value))
            self.status = "({}/{})".format(i + 1, max_value)
            self.save()

        # self.ready = True
        self.images_json = json.dumps(file_names, ensure_ascii=False)

        return True

    @staticmethod
    @Async
    def make_snapshots_async_and_save(obj, begin_time, end_time, consistency_mode):
        obj.__make_snapshots(begin_time, end_time, consistency_mode)
        obj.save()
