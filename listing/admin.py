from .models import APIConfig, GeneratedURL
from django.contrib import admin


class APIConfigAdmin(admin.ModelAdmin):
    list_display = ('url', 'user', 'password', 'template_no') 

admin.site.register(APIConfig, APIConfigAdmin)
admin.site.register(GeneratedURL)