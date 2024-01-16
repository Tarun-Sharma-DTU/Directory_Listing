from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib import admin



urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.login_view, name='login'),
    path('', views.home, name='home'),
    path('site-data/', views.site_data, name='site_data'),
    path('rest-api-test/', views.rest_api_test, name='rest_api_test'),
    path('test-status-update/', views.test_status_update, name='test_status_update'),  # URL pattern for AJAX request
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('get-task-result/<str:task_id>/', views.get_task_result, name='get_task_result'),
    path('api-config-data/', views.get_api_config_data, name='api_config_data'),
    # path('get-generated-links/', views.get_generated_links, name='get_generated_links'),
    path('get-generated-links-json/', views.get_generated_links_json, name='get-generated-links-json'),
    path('download-failed-tests/', views.download_file, name='download_failed_tests'),
    path('download-excel/', views.download_excel, name='download_excel'),



]
