from django.db import models


# Create your models here.
class Stock(models.Model):

    stock_id = models.IntegerField()

    def __str__(self):
        return str(self.stock_id)
