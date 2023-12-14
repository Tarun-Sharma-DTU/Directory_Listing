from .models import APIConfig
from django.contrib.admin import AdminSite, site




class MyAdminSite(AdminSite):
    site_header = 'Listing Admin Dashboard'

admin_site = AdminSite(name='custom_admin')

# Register your models with the custom AdminSite instance
admin_site.register(APIConfig)