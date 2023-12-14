from django.db import models

class APIConfig(models.Model):
    url = models.URLField(max_length=255)
    user = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    template_no = models.IntegerField(default=1)

    def __str__(self):
        return self.url
