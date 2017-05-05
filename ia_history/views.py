from urllib.parse import urlparse

from django.shortcuts import render
from .forms import InputForm
from .models import Snapshooter, TimelineBuilder


# Create your views here.


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

    urls_list = list(map(extract_domain, request.POST.get("urls_List").split('\r\n')))

    mode = int(request.POST.get("mode"))

    timestamp_from = "{:4}{:02}{:02}{}".format(
        int(request.POST.get("start_date_year")),
        int(request.POST.get("start_date_month")),
        int(request.POST.get("start_date_day")),
        '000000')

    timestamp_to = "{:4}{:02}{:02}{}".format(
        int(request.POST.get("end_date_year")),
        int(request.POST.get("end_date_month")),
        int(request.POST.get("end_date_day")),
        '000000')

    results = list()

    for site in urls_list:
        if not site:
            urls_list.remove(site)
            continue

        item = Snapshooter.make_snapshots(site, int(timestamp_from), int(timestamp_to), mode)
        results.append(item)

    return render(request, 'ia_history/result.html',
                  {'sites': urls_list}
                  )


def timeline(request):
    site = request.GET.get('site')
    images = TimelineBuilder.get_images_list(site)
    return render(request, 'ia_history/timeline.html', {'images': images})
