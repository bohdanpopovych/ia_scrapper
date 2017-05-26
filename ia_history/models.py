import json
import logging
import os
from io import BytesIO
from urllib.parse import urlparse

import requests
from PIL import Image
from django.db import models
from django.utils import timezone
from selenium import webdriver

from .backgrounddecorator import background


class SiteManager(models.Manager):
    def create_Site(self, site_url):
        site = Site()
        site.site_url = site_url
        return site


class Site(models.Model):
    site_url = models.CharField(max_length=100)

    images_json = models.CharField(max_length=9999)

    consistency_mode = models.IntegerField(default=0)

    status = models.CharField(max_length=50, default="(Loading...)")

    available = models.BooleanField(default=True)

    ready = models.BooleanField(default=False)

    request_date = models.DateTimeField(default=timezone.now().date())

    objects = SiteManager()

    def isAvailable(self):
        return self.available

    def isFinished(self):
        return self.ready

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
            try:
                # Here we are extracting timestamp from response
                # Since JSON, provided by archive.com is not valid, we do it manually
                # by splitting response string and selecting correct value from it
                # and replacing quotes then to have a possibility to convert them to numbers
                result = str(item.split(',')[2]).replace('"', '')
                return int(result)
            except Exception as ex:
                logger.error('Item:{}\n{}'.format(item, ex))

        site_url = self.site_url

        timemap_request_url = "http://web.archive.org/web/timemap/json/"
        parsed_uri = urlparse(site_url)

        # If url does not start from http:// or https://, we should add it manually to prevent errors
        if not parsed_uri.scheme:
            site_url = "http://" + site_url
            parsed_uri = urlparse(site_url)
        domain = '{uri.netloc}'.format(uri=parsed_uri)

        # Setting up logger
        FORMAT = '[%(asctime)-15s] %(message)s'
        logging.basicConfig(filename='info.log', level=logging.INFO, format=FORMAT)
        logger = logging.getLogger('basic')
        logger.setLevel(logging.INFO)

        # Adding consistency mode to object to know, what kind of timeline was created
        self.consistency_mode = consistency_mode

        # First we must check if site is available in archive.com cache
        # if not -- we just return (Not available) status
        if not is_available(site_url):
            logging.error('{} not available.'.format(site_url))
            self.status = "(Not available)"
            self.images_json = "{}"
            self.available = False
            self.ready = True
            self.save()
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
                key = str(temp_timestamps[i])[0:6]
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
        folder = 'media/{}_{}'.format(domain, consistency_mode)

        if not os.path.exists(folder):
            logger.info("Directory '{}' does not exists, creating...".format(folder))
            os.makedirs(folder)
        else:
            # Removing existing files from folder
            for the_file in os.listdir(folder):
                file_path = os.path.join(folder, the_file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    pass

        file_names = dict()

        max_value = len(timestamps)
        logger.info("Total snapshots: {}".format(max_value))

        self.status = "({}/{})".format(0, max_value)
        self.save()

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

            file_name = '{}/snapshot_{}.jpg'.format(folder, timestamp)
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

        self.ready = True
        self.images_json = json.dumps(file_names, ensure_ascii=False)

        self.save()

        logger.info("{} finished!".format(domain))
        return True

    @background
    def make_snapshots_in_background(self, begin_time, end_time, consistency_mode):
        return self.__make_snapshots(begin_time, end_time, consistency_mode)
