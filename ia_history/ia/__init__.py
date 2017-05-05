import os
import requests
from urllib.parse import urlparse
from selenium import webdriver


def make_snapshots(site_url, begin_time, end_time, consistency_mode=0):
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

    timemap_request_url = "http://web.archive.org/web/timemap/json/"

    # First we must check if site is available in archive.com cache
    if not is_available(site_url):
        return False

    # First slice -- [2:-3] -- is to remove incorrect characters at the beginning: "b'" and "'\n"
    # Second slice -- [1:] -- is to remove first element, which contains only field names,
    # since we don't need it
    response_list = str(requests.get(timemap_request_url + site_url).content)[2:-3].split("\\n")[1:]

    # Extracting timestamps from response content
    # and filtering them to fit begin_time and end_time
    # if mode == 3
    timestamps = list()
    if consistency_mode == 3:
        timestamps = list(filter(lambda x: begin_time <= x <= end_time, list(map(extract_timestamp, response_list))))
    elif consistency_mode == 2:
        timestamps = list(map(extract_timestamp, response_list))
    elif consistency_mode == 1:
        temp_timestamps = list(map(extract_timestamp, response_list))
        timestamps_dict = dict()

        for i in range(0, len(temp_timestamps)):
            key = str(temp_timestamps[i])[4:6]
            timestamps_dict[key] = temp_timestamps[i]

        timestamps = temp_timestamps
    elif consistency_mode == 0:
        temp_timestamps = list(map(extract_timestamp, response_list))
        timestamps_dict = dict()

        for i in range(0, len(temp_timestamps)):
            key = str(temp_timestamps[i])[0:4]
            timestamps_dict[key] = temp_timestamps[i]

        timestamps = temp_timestamps

    driver = webdriver.PhantomJS()

    parsed_uri = urlparse(site_url)
    domain = '{uri.netloc}'.format(uri=parsed_uri)

    # Creating separate directory for site if not exist
    if not os.path.exists(domain):
        os.makedirs(domain)

    file_names = dict()

    for i, timestamp in enumerate(timestamps):
        # max_value = len(timestamps)

        snapshot_url = "https://web-beta.archive.org/web/{}/{}".format(timestamp, site_url)
        driver.get(snapshot_url)

        # This script adds default background to page, since PhantomJS can do "transparent" snapshot sometimes,
        # and removes archive.com top block from page (last line)
        driver.execute_script("""(function() {
            var style = document.createElement('style'), text = document.createTextNode('body { background: #fff }');
            style.setAttribute('type', 'text/css');
            style.appendChild(text);
            document.head.insertBefore(style, document.head.firstChild);
            
            obj = document.getElementById("wm-ipp");
            if (document.contains(obj) &&
                obj !== 'null' &&
                obj !== 'undefined') {
                obj.remove();
            }
        })();""")
        driver.set_window_size(1024, 768)
        file_name = '{}/snapshot_{}.png'.format(domain, timestamp)
        driver.save_screenshot(file_name)
        file_names[timestamp] = domain

    return file_names
