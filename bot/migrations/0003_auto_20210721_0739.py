# Generated by Django 3.2.5 on 2021-07-21 07:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0002_auto_20210721_0739'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stock',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='stock',
            name='last_name',
        ),
    ]