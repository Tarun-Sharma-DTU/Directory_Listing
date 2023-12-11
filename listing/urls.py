from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('site-data', views.site_data, name='site_data'),
]
