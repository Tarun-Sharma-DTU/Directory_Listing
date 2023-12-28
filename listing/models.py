from django.db import models
from django.conf import settings



class APIConfig(models.Model):
    url = models.CharField(max_length=255)
    user = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    template_no = models.IntegerField(default=1)

    def __str__(self):
        return self.url
    

class GeneratedURL(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.url
