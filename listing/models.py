from django.db import models
from django.conf import settings



class APIConfig(models.Model):
    website = models.CharField(max_length=255, unique=True, null=True)
    user = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    template_no = models.IntegerField(default=1)
    site_enable = models.BooleanField(default=True, verbose_name="Site Enable")


    def __str__(self):
        return self.website
    

class GeneratedURL(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.url
    
class TestResult(models.Model):
    config = models.ForeignKey(APIConfig, on_delete=models.CASCADE)
    status = models.CharField(max_length=100)

class WebsiteData(models.Model):
    api_config = models.ForeignKey(APIConfig, on_delete=models.CASCADE, related_name='website_data')
    company_names = models.TextField()  # Stores a JSON-encoded list of company names
    company_websites = models.TextField()  # Stores a JSON-encoded list of company websites

    def __str__(self):
        return self.api_config.website

