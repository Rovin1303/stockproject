from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from .models import Portfolio, Stock
from .serializers import PortfolioSerializer, StockSerializer
from eda.services.stock_service import get_stock_analysis
from eda.services.regression_service import (
    predict_next_day_logistic_window,
    predict_next_day_price,
    tomorrow_date_str,
)


def _clean_last_30_prices(price_history):
    prices = []
    for value in price_history or []:
        try:
            prices.append(float(value))
        except (TypeError, ValueError):
            continue
    return prices[-30:]


def _clean_prices(price_history):
    prices = []
    for value in price_history or []:
        try:
            prices.append(float(value))
        except (TypeError, ValueError):
            continue
    return prices


def _sync_stock_market_fields(stock, analysis):
    if not analysis:
        return

    stock.company_name = analysis.get("company_name") or stock.company_name
    stock.current_price = analysis.get("current_price") or stock.current_price
    stock.pe_ratio = analysis.get("pe_ratio") or 0
    stock.high_52w = analysis.get("high_52w")
    stock.low_52w = analysis.get("low_52w")
    stock.price_history_30 = _clean_last_30_prices(analysis.get("price_history"))
    stock.save(
        update_fields=[
            "company_name",
            "current_price",
            "pe_ratio",
            "high_52w",
            "low_52w",
            "price_history_30",
        ]
    )


def _compute_volatility_pct(prices, lookback_days):
    if len(prices) <= lookback_days:
        return None

    window = prices[-(lookback_days + 1):]
    arr = np.array(window, dtype=float)
    if arr.size < 2:
        return None

    prev = arr[:-1]
    curr = arr[1:]
    valid = prev != 0
    if not np.any(valid):
        return None

    returns = (curr[valid] / prev[valid]) - 1.0
    if returns.size == 0:
        return None
    return float(np.std(returns) * 100.0)


def _compute_max_drawdown_pct(prices, lookback_days):
    if len(prices) <= lookback_days:
        return None

    window = np.array(prices[-(lookback_days + 1):], dtype=float)
    if window.size < 2:
        return None

    running_max = np.maximum.accumulate(window)
    valid = running_max != 0
    if not np.any(valid):
        return None

    drawdowns = np.zeros_like(window, dtype=float)
    drawdowns[valid] = (window[valid] / running_max[valid]) - 1.0
    max_drawdown = float(np.min(drawdowns))
    return abs(max_drawdown) * 100.0


def _cluster_by_multi_returns(items):
    if not items:
        return items

    X = np.array(
        [
            [item["vol_21"], item["max_drawdown_126"], item.get("discount_pct", 0.0)]
            for item in items
        ],
        dtype=float,
    )
    X_scaled = StandardScaler().fit_transform(X)

    if len(items) >= 3:
        model = KMeans(n_clusters=3, random_state=42, n_init=10)
        labels = model.fit_predict(X_scaled)
        centers = model.cluster_centers_
        # Higher vol/drawdown/discount contributes to higher risk grouping.
        center_scores = centers.mean(axis=1)
        order = np.argsort(center_scores)
        cluster_name_map = {
            int(order[0]): "Low Risk",
            int(order[1]): "Medium Risk",
            int(order[2]): "High Risk",
        }
        for item, raw_label in zip(items, labels):
            item["cluster"] = cluster_name_map[int(raw_label)]
    else:
        sorted_items = sorted(
            items,
            key=lambda x: (x["vol_21"] + x["max_drawdown_126"]) / 2.0,
        )
        names = ["Low Risk", "Medium Risk", "High Risk"]
        for idx, item in enumerate(sorted_items):
            item["cluster"] = names[min(idx, 2)]

    return items


def _stock_comparison_payload(stock):
    analysis = get_stock_analysis(stock.ticker) or {}
    _sync_stock_market_fields(stock, analysis)
    prices = _clean_last_30_prices(analysis.get("price_history"))
    if len(prices) < 2:
        return {
            "stock_id": stock.id,
            "ticker": stock.ticker,
            "company_name": stock.company_name,
            "error": "Not enough history",
        }

    start_price = prices[0]
    end_price = prices[-1]
    returns_pct = ((end_price - start_price) / start_price) * 100 if start_price else 0.0
    predicted_price = predict_next_day_price(prices)
    predicted_direction = "UP" if predicted_price and predicted_price >= end_price else "DOWN"

    return {
        "stock_id": stock.id,
        "ticker": stock.ticker,
        "company_name": analysis.get("company_name") or stock.company_name,
        "current_price": analysis.get("current_price") or stock.current_price,
        "high_52w": analysis.get("high_52w"),
        "low_52w": analysis.get("low_52w"),
        "pe_ratio": analysis.get("pe_ratio"),
        "market_cap": analysis.get("market_cap"),
        "returns_pct_30d": round(returns_pct, 2),
        "predicted_price_next_day": predicted_price,
        "predicted_direction": predicted_direction,
        "lookback_days": len(prices),
    }


# ===============================
# PORTFOLIO LIST + CREATE
# ===============================
class PortfolioView(APIView):

    def get(self, request):
        portfolios = Portfolio.objects.all()
        serializer = PortfolioSerializer(portfolios, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = PortfolioSerializer(data=request.data)
        if serializer.is_valid():
            portfolio = serializer.save()
            return Response(PortfolioSerializer(portfolio).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===============================
# PORTFOLIO DETAIL (GET, PUT, DELETE)
# ===============================
class PortfolioDetailView(APIView):

    def get_object(self, pk):
        try:
            return Portfolio.objects.get(pk=pk)
        except Portfolio.DoesNotExist:
            return None

    def get(self, request, pk):
        portfolio = self.get_object(pk)
        if not portfolio:
            return Response({"error": "Portfolio not found"}, status=404)

        # Live fetch from yfinance and store latest values in DB on each request.
        for stock in portfolio.stocks.all():
            analysis = get_stock_analysis(stock.ticker)
            _sync_stock_market_fields(stock, analysis)

        serializer = PortfolioSerializer(portfolio)
        return Response(serializer.data)

    def put(self, request, pk):
        portfolio = self.get_object(pk)
        if not portfolio:
            return Response({"error": "Portfolio not found"}, status=404)

        serializer = PortfolioSerializer(portfolio, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Portfolio updated successfully"})
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        portfolio = self.get_object(pk)
        if not portfolio:
            return Response({"error": "Portfolio not found"}, status=404)

        portfolio.delete()
        return Response({"message": "Portfolio deleted successfully"})


# ===============================
# STOCK LIST + CREATE
# ===============================
class StockView(APIView):

    def get(self, request):
        stocks = Stock.objects.all()
        serializer = StockSerializer(stocks, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = StockSerializer(data=request.data)
        if serializer.is_valid():
            stock = serializer.save()
            return Response(StockSerializer(stock).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===============================
# STOCK DETAIL (GET, PUT, DELETE)
# ===============================
class StockDetailView(APIView):

    def get_object(self, pk):
        try:
            return Stock.objects.get(pk=pk)
        except Stock.DoesNotExist:
            return None

    def get(self, request, pk):
        stock = self.get_object(pk)
        if not stock:
            return Response({"error": "Stock not found"}, status=404)

        serializer = StockSerializer(stock)
        return Response(serializer.data)

    def put(self, request, pk):
        stock = self.get_object(pk)
        if not stock:
            return Response({"error": "Stock not found"}, status=404)

        serializer = StockSerializer(stock, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Stock updated successfully"})
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        stock = self.get_object(pk)
        if not stock:
            return Response({"error": "Stock not found"}, status=404)

        stock.delete()
        return Response({"message": "Stock deleted successfully"})


class PortfolioPredictionView(APIView):
    def get(self, request, pk):
        try:
            portfolio = Portfolio.objects.get(pk=pk)
        except Portfolio.DoesNotExist:
            return Response({"error": "Portfolio not found"}, status=404)

        next_date = tomorrow_date_str()
        predictions = []

        for stock in portfolio.stocks.all():
            analysis = get_stock_analysis(stock.ticker)
            _sync_stock_market_fields(stock, analysis)
            history = stock.price_history_30 or []
            predicted_price = predict_next_day_price(history)

            predictions.append(
                {
                    "stock_id": stock.id,
                    "date_tom": next_date,
                    "price_predict": predicted_price,
                }
            )

        return Response(predictions, status=200)


class PortfolioLogisticView(APIView):
    def get(self, request, pk):
        try:
            portfolio = Portfolio.objects.get(pk=pk)
        except Portfolio.DoesNotExist:
            return Response({"error": "Portfolio not found"}, status=404)

        next_date = tomorrow_date_str()
        output = []

        for stock in portfolio.stocks.all():
            analysis = get_stock_analysis(stock.ticker)
            _sync_stock_market_fields(stock, analysis)
            history = analysis.get("price_history") if analysis else []
            logistic = predict_next_day_logistic_window(history, window_size=30)

            output.append(
                {
                    "stock_id": stock.id,
                    "ticker": stock.ticker,
                    "company_name": stock.company_name,
                    "date_tom": next_date,
                    "window_size": logistic["window_size"] if logistic else 30,
                    "samples": logistic["samples"] if logistic else 0,
                    "probability_up": logistic["probability_up"] if logistic else None,
                    "probability_down": logistic["probability_down"] if logistic else None,
                    "predicted_class": logistic["predicted_class"] if logistic else None,
                    "predicted_label": logistic["predicted_label"] if logistic else None,
                }
            )

        return Response(output, status=200)


class PortfolioClusterView(APIView):
    def get(self, request, pk):
        try:
            portfolio = Portfolio.objects.get(pk=pk)
        except Portfolio.DoesNotExist:
            return Response({"error": "Portfolio not found"}, status=404)

        rows = []
        for stock in portfolio.stocks.all():
            analysis = get_stock_analysis(stock.ticker)
            _sync_stock_market_fields(stock, analysis)
            prices = _clean_prices(analysis.get("price_history") if analysis else [])
            if len(prices) < 127:
                continue

            vol_21 = _compute_volatility_pct(prices, 21)
            max_dd_126 = _compute_max_drawdown_pct(prices, 126)
            if vol_21 is None or max_dd_126 is None:
                continue

            analysis_high = analysis.get("high_52w") if analysis else None
            analysis_current = analysis.get("current_price") if analysis else None
            high_52w = analysis_high if analysis_high not in (None, 0) else stock.high_52w
            current_price = analysis_current if analysis_current not in (None, 0) else stock.current_price

            # Fallback to available history so discount can still be derived.
            if not high_52w and prices:
                high_52w = max(prices)
            if not current_price and prices:
                current_price = prices[-1]

            discount_pct = None
            if high_52w and current_price is not None:
                discount_pct = ((float(high_52w) - float(current_price)) / float(high_52w)) * 100

            rows.append(
                {
                    "stock_id": stock.id,
                    "ticker": stock.ticker,
                    "company_name": stock.company_name,
                    "vol_21": round(float(vol_21), 2),
                    "max_drawdown_126": round(float(max_dd_126), 2),
                    "discount_pct": round(float(discount_pct), 2) if discount_pct is not None else None,
                    "cluster": None,
                }
            )

        rows = _cluster_by_multi_returns(rows)
        cluster_counts = {"High Risk": 0, "Medium Risk": 0, "Low Risk": 0}
        for item in rows:
            label = item.get("cluster")
            if label in cluster_counts:
                cluster_counts[label] += 1

        return Response(
            {
                "portfolio_id": portfolio.id,
                "total_stocks_clustered": len(rows),
                "cluster_counts": cluster_counts,
                "stocks": rows,
            },
            status=200,
        )


class PortfolioComparisonView(APIView):
    def get(self, request, pk):
        try:
            portfolio = Portfolio.objects.get(pk=pk)
        except Portfolio.DoesNotExist:
            return Response({"error": "Portfolio not found"}, status=404)

        stock1_id = request.query_params.get("stock1_id")
        stock2_id = request.query_params.get("stock2_id")
        if not stock1_id or not stock2_id:
            return Response({"error": "stock1_id and stock2_id are required"}, status=400)

        if stock1_id == stock2_id:
            return Response({"error": "Select two different stocks"}, status=400)

        stock1 = portfolio.stocks.filter(id=stock1_id).first()
        stock2 = portfolio.stocks.filter(id=stock2_id).first()
        if not stock1 or not stock2:
            return Response({"error": "Stocks must belong to this portfolio"}, status=400)

        result = {
            "portfolio_id": portfolio.id,
            "stock_1": _stock_comparison_payload(stock1),
            "stock_2": _stock_comparison_payload(stock2),
        }
        return Response(result, status=200)
