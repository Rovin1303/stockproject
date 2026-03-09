from django.urls import path
from .views import (
    PortfolioClusterView,
    PortfolioView,
    PortfolioDetailView,
    PortfolioComparisonView,
    PortfolioLogisticView,
    PortfolioPredictionView,
    StockTimeSeriesForecastView,
    StockView,
    StockDetailView
)

urlpatterns = [
    path('portfolio/', PortfolioView.as_view()),
    path('portfolio/<int:pk>/', PortfolioDetailView.as_view()),
    path('portfolio/<int:pk>/predictions/', PortfolioPredictionView.as_view()),
    path('portfolio/<int:pk>/logistic/', PortfolioLogisticView.as_view()),
    path('portfolio/<int:pk>/clusters/', PortfolioClusterView.as_view()),
    path('portfolio/<int:pk>/compare/', PortfolioComparisonView.as_view()),
    path('timeseries/predict/', StockTimeSeriesForecastView.as_view()),

    path('stocks/', StockView.as_view()),
    path('stocks/<int:pk>/', StockDetailView.as_view()),
]
