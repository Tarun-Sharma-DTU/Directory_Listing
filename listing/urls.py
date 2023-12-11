from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('', views.home, name='home'),
    path('site-data', views.site_data, name='site_data'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),


]
