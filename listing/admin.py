from .models import APIConfig, GeneratedURL, WebsiteData, CompanyURL, PostedWebsite
from django.contrib import admin


class APIConfigAdmin(admin.ModelAdmin):
    list_display = ('website', 'user', 'password', 'template_no', 'site_enable') 

admin.site.register(APIConfig, APIConfigAdmin)
admin.site.register(GeneratedURL)
admin.site.register(WebsiteData)
admin.site.register(CompanyURL)
admin.site.register(PostedWebsite)