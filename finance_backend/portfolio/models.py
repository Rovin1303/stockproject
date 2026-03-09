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


class TimeSeriesForecast(models.Model):
    FORECAST_OPTIONS = (
        (1, "ts_1"),
        (7, "ts_7"),
    )

    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name="timeseries_forecasts",
    )
    forecast_type = models.CharField(max_length=10)
    horizon_days = models.IntegerField(choices=FORECAST_OPTIONS)
    model_name = models.CharField(max_length=50, default="ARIMA")
    predicted_for_date = models.DateField()
    forecast_prices = models.JSONField(default=list, blank=True)
    history_prices = models.JSONField(default=list, blank=True)
    history_dates = models.JSONField(default=list, blank=True)
    forecast_dates = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("stock", "forecast_type", "predicted_for_date")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.stock.ticker} {self.forecast_type} {self.predicted_for_date}"
