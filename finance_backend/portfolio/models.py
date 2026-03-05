from django.db import models
from staff.models import Staff


class Portfolio(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(Staff, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Stock(models.Model):
    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="stocks"
    )

    company_name = models.CharField(max_length=200)
    ticker = models.CharField(max_length=20)

    current_price = models.FloatField()
    pe_ratio = models.FloatField()
    high_52w = models.FloatField(null=True, blank=True)
    low_52w = models.FloatField(null=True, blank=True)
    price_history_30 = models.JSONField(default=list, blank=True)
    predicted_price = models.FloatField(null=True, blank=True)
    predicted_for_date = models.DateField(null=True, blank=True)
    intrinsic_value = models.FloatField(null=True, blank=True)

    def discount_level(self):
        if self.intrinsic_value:
            return ((self.intrinsic_value - self.current_price) / self.intrinsic_value) * 100
        return 0

    def __str__(self):
        return self.company_name

    class Meta:
        unique_together = ("portfolio", "ticker")
