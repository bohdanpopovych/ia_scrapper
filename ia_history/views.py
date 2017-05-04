from django.shortcuts import render
from ia_history.ia import make_snapshots
from .forms import InputForm


# Create your views here.


def index(request):
    form = InputForm
    return render(request, 'ia_history/index.html', {'form': form})


def result(request):
    urls_list = request.POST.get("urls_List").split('\r\n')

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
        results.append(make_snapshots(site, timestamp_from, timestamp_to, mode))

    render(request, 'ia_history/timeline.html', {'date': results})

    return render(request, 'ia_history/result.html', {'text': urls_list})
