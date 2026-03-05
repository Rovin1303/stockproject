
from django.db import models

class StockAnalysis(models.Model):
    ticker = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ticker