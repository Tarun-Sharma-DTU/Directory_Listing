# Generated by Django 4.2.7 on 2024-01-14 03:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listing', '0005_testresult'),
    ]

    operations = [
        migrations.AddField(
            model_name='apiconfig',
            name='site_enable',
            field=models.BooleanField(default=True, verbose_name='Site Enable'),
        ),
    ]
