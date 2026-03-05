from django.urls import path
from .views import (
    GoldSilverCorrelationAPIView,
    StockDetailAPIView,
    StockSearchAPIView,
)

urlpatterns = [
    path('stock/<int:stock_id>/', StockDetailAPIView.as_view()),
    path('search/', StockSearchAPIView.as_view()),
    path('metals/correlation/', GoldSilverCorrelationAPIView.as_view()),
]
