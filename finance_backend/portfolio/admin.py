from django.contrib import admin
from .models import Portfolio, Stock, TimeSeriesForecast


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_by")
    search_fields = ("name",)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("id", "ticker", "company_name", "portfolio", "current_price")
    list_filter = ("portfolio",)
    search_fields = ("ticker", "company_name")


@admin.register(TimeSeriesForecast)
class TimeSeriesForecastAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "stock",
        "forecast_type",
        "horizon_days",
        "predicted_for_date",
        "created_at",
    )
    list_filter = ("forecast_type", "horizon_days")
    search_fields = ("stock__ticker", "stock__company_name")
