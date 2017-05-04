from django import forms
from django.forms.extras.widgets import SelectDateWidget


class InputForm(forms.Form):
    urls_List = forms.CharField(label="", widget=forms.Textarea)

    CHOICES = [(0, 'One per Year'),
               (1, 'One per month'),
               (2, 'All available timestamps'),
               (3, 'All timestamps: ')]

    mode = forms.ChoiceField(choices=CHOICES, widget=forms.RadioSelect)

    start_date = forms.DateField(widget=SelectDateWidget, label="From")
    end_date = forms.DateField(widget=SelectDateWidget, label="To")



