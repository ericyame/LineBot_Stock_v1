from django.conf import settings
from django.db import models


class Stock(models.Model):
    default_user_id = 1
    stock_id = models.IntegerField()
    user_id = models.CharField(max_length=255, default=default_user_id)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user_id', 'stock_id'], name='unique_user_stock')
        ]

    def __str__(self):
        return f"{self.stock_id} ({self.user_id})"
