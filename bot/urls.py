from django.conf.urls import include, url
from django.urls import path
from . import views

urlpatterns = [
    url('^callback/', views.callback),
    url('^push_notification/', views.push_notification),
]
