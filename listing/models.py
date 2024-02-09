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
    author_name = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.url
    
class TestResult(models.Model):
    config = models.ForeignKey(APIConfig, on_delete=models.CASCADE)
    status = models.CharField(max_length=100)

class WebsiteData(models.Model):
    api_config = models.ForeignKey(APIConfig, on_delete=models.CASCADE, related_name='website_data', null=True, blank=True)
    company_websites = models.TextField(null=True, blank=True)  # Stores a JSON-encoded list of company websites

    def __str__(self):
        return self.api_config.website
    
class CompanyURL(models.Model):
    generated_url = models.URLField(max_length=2048, null=True, blank=True) 
    company_website = models.URLField(max_length=2048, null=True, blank=True)

    def __str__(self):
        return f"{self.generated_url} - Linked to - {self.company_website}"
    

class PostedWebsite(models.Model):
    website = models.ForeignKey(APIConfig, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.website:
            return self.website.website
        return "No website associated"