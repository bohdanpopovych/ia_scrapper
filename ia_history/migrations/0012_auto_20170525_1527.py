# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-25 15:27
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ia_history', '0011_site_request_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='consistency_mode',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='site',
            name='request_date',
            field=models.DateTimeField(default=datetime.date(2017, 5, 25)),
        ),
    ]
