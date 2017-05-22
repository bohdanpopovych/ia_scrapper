from json import loads
from urllib.parse import urlparse

from django.shortcuts import render, render_to_response

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

    # removing all data from operations, made earlier
    # Site.objects.all().delete()

    for site in urls_list:
        if not site:
            urls_list.remove(site)
        else:
            site_obj, created = Site.objects.get_or_create(site_url=site)

            if not created:
                site_obj.delete()

            site_obj.make_snapshots_async_and_save(site_obj, begin_time, end_time, consistency_mode)

    return render(request, 'ia_history/result.html',
                  {'total_count': len(urls_list)}
                  )


def timeline(request):

    def timestamp_to_text(file_name):
        # Function to provide link text from timestamp
        timestamp = file_name.split('_')[1].split('.')[0]

        year = timestamp[0:4]
        month = timestamp[4:6]
        day = timestamp[6:8]

        return "{}/{}/{}".format(month, day, year)

    site = request.GET.get('site')

    def make_link_to_timestamp(file_name):
        timestamp = file_name.split('_')[1].split('.')[0]
        return "https://web.archive.org/web/{}/{}".format(timestamp, site)

    site_obj = Site.objects.filter(site_url=site)[0]

    if not site_obj.isAvailable():
        return render(request, 'ia_history/not_available.html', {
            'site': site_obj.site_url
        })

    images = loads(site_obj.images_json)
    links = list(map(make_link_to_timestamp, images))
    labels = list(map(timestamp_to_text, images))

    zipped_result = zip(images, links, labels)

    return render(request, 'ia_history/timeline.html', {'images': zipped_result})


def resultdiv(request):
    all_sites = Site.objects.all()
    # ready_sites = list()
    # for item in all_sites:
    #     if item.isReady():
    #         ready_sites.append(item.site_url)

    return render_to_response('ia_history/resultdiv.html',
                              {'sites': all_sites})
