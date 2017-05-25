import os
from collections import defaultdict
from datetime import datetime
from json import loads
from urllib.parse import urlparse

from django.http import HttpResponse
from django.shortcuts import render, render_to_response
from django.utils import timezone

from .forms import InputForm
from .models import Site


def index(request):
    form = InputForm
    return render(request, 'ia_history/index.html', {'form': form})


def result(request):
    def extract_domain(site_url):
        parsed_uri = urlparse(site_url)

        # If url does not start from http:// or https://, we should add it manually to prevent errors
        if not parsed_uri.scheme:
            site_url = "http://" + site_url
            parsed_uri = urlparse(site_url
                                  )
        return '{uri.netloc}'.format(uri=parsed_uri)

    if request.is_ajax():
        return resultdiv(request)

    temp = request.POST.get('urls_List')

    if temp:

        urls_list = list(map(extract_domain, request.POST.get("urls_List").split('\r\n')))

        consistency_mode = int(request.POST.get("mode"))

        begin_time = int("{:4}{:02}{:02}{}".format(
            int(request.POST.get("start_date_year")),
            int(request.POST.get("start_date_month")),
            int(request.POST.get("start_date_day")),
            '000000'))

        end_time = int("{:4}{:02}{:02}{}".format(
            int(request.POST.get("end_date_year")),
            int(request.POST.get("end_date_month")),
            int(request.POST.get("end_date_day")),
            '000000'))

        for site in urls_list:
            if not site:
                urls_list.remove(site)
            else:
                site_obj, created = Site.objects.get_or_create(
                    site_url=site,
                    consistency_mode=consistency_mode,
                    request_date=timezone.now().date()
                )

                if not created:
                    if site_obj.isFinished() and site_obj.consistency_mode == consistency_mode:
                        # Removing object from DB and files from folder in case user already made
                        # one timeline of this site and now wants another one
                        site_obj.delete()

                site_obj.make_snapshots_in_background(
                    begin_time, end_time, consistency_mode)

    return render(request, 'ia_history/result.html', {})


def timeline(request):

    def timestamp_to_text(file_name):
        # Function to provide link text from timestamp
        timestamp = file_name.split('_')[-1].split('.')[0]

        year = timestamp[0:4]
        month = timestamp[4:6]
        day = timestamp[6:8]

        return "{}/{}/{}".format(month, day, year)

    site = request.GET.get('site')

    try:

        def make_link_to_timestamp(file_name):
            timestamp = file_name.split('_')[-1].split('.')[0]
            return "https://web.archive.org/web/{}/{}".format(timestamp, site)

        site_obj = Site.objects.filter(site_url=site)[0]

        if not site_obj.isAvailable():
            return render(request, 'ia_history/not_available.html', {
                'site': site_obj.site_url
            })

        images = sorted(loads(site_obj.images_json), reverse=True)
        links = list(map(make_link_to_timestamp, images))
        labels = list(map(timestamp_to_text, images))

        zipped_result = zip(images, links, labels)

        return render(request, 'ia_history/timeline.html',
                      {'images': zipped_result,
                       'site': site})

    except Exception as ex:
        return render(request, 'ia_history/timeline_not_finished.html',
                      {'site': site})


def resultdiv(request):
    all_sites = Site.objects.all().order_by('request_date')
    request_dates = defaultdict(list)

    for site in all_sites:
        request_dates[site.request_date.strftime("%Y-%m-%d")].append(site)

    zipped = zip(request_dates.keys(), request_dates.values())

    return render_to_response('ia_history/resultdiv.html', {'dates': zipped})


def remove(request):
    site = request.GET.get('site')
    site_date_str = request.GET.get('date')
    consistency_mode = request.GET.get('mode')
    site_date = datetime.strptime(site_date_str, '%Y-%m-%d')
    site_obj = Site.objects.filter(site_url=site, request_date=site_date).first()

    folder = str()

    if site_obj:
        site_obj.delete()
        folder = 'media/{}_{}'.format(site, consistency_mode)

    if os.path.exists(folder):
        # Removing existing files from folder
        for the_file in os.listdir(folder):
            file_path = os.path.join(folder, the_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                pass

    return HttpResponse('')



