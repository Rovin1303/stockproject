from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from .models import Portfolio, Stock, TimeSeriesForecast
from .serializers import PortfolioSerializer, StockSerializer
from staff.models import Staff
from eda.services.stock_service import get_stock_analysis
from eda.services.arima_timeseries import predict_stock_timeseries
from eda.services.rnn_timeseries import predict_stock_timeseries_rnn
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
            [item["vol_21"], item["max_drawdown_126"]]
            for item in items
        ],
        dtype=float,
    )
    X_scaled = StandardScaler().fit_transform(X)

    if len(items) >= 3:
        model = KMeans(n_clusters=3, random_state=42, n_init=10)
        labels = model.fit_predict(X_scaled)
        centers = model.cluster_centers_
        # Higher vol/drawdown means higher risk.
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


def _extract_staff_id(request):
    raw = (
        request.query_params.get("staff_id")
        or request.headers.get("X-Staff-Id")
        or request.data.get("staff_id")
        or request.data.get("created_by")
    )
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _get_request_staff(request):
    staff_id = _extract_staff_id(request)
    if not staff_id:
        return None
    return Staff.objects.filter(id=staff_id).first()


# ===============================
# PORTFOLIO LIST + CREATE
# ===============================
class PortfolioView(APIView):

    def get(self, request):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolios = Portfolio.objects.filter(created_by=staff).order_by("-id")
        serializer = PortfolioSerializer(portfolios, many=True)
        return Response(serializer.data)

    def post(self, request):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        serializer = PortfolioSerializer(data=request.data)
        if serializer.is_valid():
            portfolio = serializer.save(created_by=staff)
            return Response(PortfolioSerializer(portfolio).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===============================
# PORTFOLIO DETAIL (GET, PUT, DELETE)
# ===============================
class PortfolioDetailView(APIView):

    def get_object(self, pk, staff):
        return Portfolio.objects.filter(pk=pk, created_by=staff).first()

    def get(self, request, pk):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolio = self.get_object(pk, staff)
        if not portfolio:
            return Response({"error": "Portfolio not found"}, status=404)

        # Live fetch from yfinance and store latest values in DB on each request.
        for stock in portfolio.stocks.all():
            analysis = get_stock_analysis(stock.ticker)
            _sync_stock_market_fields(stock, analysis)

        serializer = PortfolioSerializer(portfolio)
        return Response(serializer.data)

    def put(self, request, pk):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolio = self.get_object(pk, staff)
        if not portfolio:
            return Response({"error": "Portfolio not found"}, status=404)

        serializer = PortfolioSerializer(portfolio, data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=staff)
            return Response({"message": "Portfolio updated successfully"})
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolio = self.get_object(pk, staff)
        if not portfolio:
            return Response({"error": "Portfolio not found"}, status=404)

        portfolio.delete()
        return Response({"message": "Portfolio deleted successfully"})


# ===============================
# STOCK LIST + CREATE
# ===============================
class StockView(APIView):

    def get(self, request):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        stocks = Stock.objects.filter(portfolio__created_by=staff).select_related("portfolio")
        serializer = StockSerializer(stocks, many=True)
        return Response(serializer.data)

    def post(self, request):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolio_id = request.data.get("portfolio")
        if not Portfolio.objects.filter(id=portfolio_id, created_by=staff).exists():
            return Response({"error": "Invalid portfolio for this user"}, status=403)

        serializer = StockSerializer(data=request.data)
        if serializer.is_valid():
            stock = serializer.save()
            return Response(StockSerializer(stock).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===============================
# STOCK DETAIL (GET, PUT, DELETE)
# ===============================
class StockDetailView(APIView):

    def get_object(self, pk, staff):
        return Stock.objects.filter(pk=pk, portfolio__created_by=staff).first()

    def get(self, request, pk):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        stock = self.get_object(pk, staff)
        if not stock:
            return Response({"error": "Stock not found"}, status=404)

        serializer = StockSerializer(stock)
        return Response(serializer.data)

    def put(self, request, pk):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        stock = self.get_object(pk, staff)
        if not stock:
            return Response({"error": "Stock not found"}, status=404)

        serializer = StockSerializer(stock, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Stock updated successfully"})
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        stock = self.get_object(pk, staff)
        if not stock:
            return Response({"error": "Stock not found"}, status=404)

        stock.delete()
        return Response({"message": "Stock deleted successfully"})


class PortfolioPredictionView(APIView):
    def get(self, request, pk):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolio = Portfolio.objects.filter(pk=pk, created_by=staff).first()
        if not portfolio:
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
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolio = Portfolio.objects.filter(pk=pk, created_by=staff).first()
        if not portfolio:
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
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolio = Portfolio.objects.filter(pk=pk, created_by=staff).first()
        if not portfolio:
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

            rows.append(
                {
                    "stock_id": stock.id,
                    "ticker": stock.ticker,
                    "company_name": stock.company_name,
                    "vol_21": round(float(vol_21), 2),
                    "max_drawdown_126": round(float(max_dd_126), 2),
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
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        portfolio = Portfolio.objects.filter(pk=pk, created_by=staff).first()
        if not portfolio:
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


class StockTimeSeriesForecastView(APIView):
    def get(self, request):
        staff = _get_request_staff(request)
        if not staff:
            return Response({"error": "Valid staff_id is required"}, status=401)

        stock_id = request.query_params.get("stock_id")
        forecast_type = (request.query_params.get("forecast_type") or "ts_1").strip().lower()
        model_type = (request.query_params.get("model_type") or "arima").strip().lower()

        if not stock_id:
            return Response({"error": "stock_id is required"}, status=400)

        if forecast_type not in ("ts_1", "ts_7"):
            return Response({"error": "forecast_type must be ts_1 or ts_7"}, status=400)

        if model_type not in ("arima", "rnn"):
            return Response({"error": "model_type must be arima or rnn"}, status=400)

        horizon_days = 1 if forecast_type == "ts_1" else 7

        try:
            stock = Stock.objects.select_related("portfolio").get(
                pk=stock_id,
                portfolio__created_by=staff,
            )
        except Stock.DoesNotExist:
            return Response({"error": "Stock not found"}, status=404)

        analysis = get_stock_analysis(stock.ticker)
        if not analysis:
            return Response({"error": "Unable to fetch latest stock history"}, status=400)

        _sync_stock_market_fields(stock, analysis)

        try:
            if model_type == "rnn":
                forecast_payload = predict_stock_timeseries_rnn(
                    price_history=analysis.get("price_history") or [],
                    date_history=analysis.get("dates") or [],
                    horizon_days=horizon_days,
                    open_history=analysis.get("open_history") or [],
                    high_history=analysis.get("high_history") or [],
                    low_history=analysis.get("low_history") or [],
                    volume_history=analysis.get("volume_history") or [],
                )
            else:
                forecast_payload = predict_stock_timeseries(
                    price_history=analysis.get("price_history") or [],
                    date_history=analysis.get("dates") or [],
                    horizon_days=horizon_days,
                )
        except RuntimeError as exc:
            return Response({"error": str(exc)}, status=400)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        forecast_obj, _ = TimeSeriesForecast.objects.update_or_create(
            stock=stock,
            forecast_type=forecast_type,
            predicted_for_date=forecast_payload["predicted_for_date"],
            defaults={
                "horizon_days": horizon_days,
                "model_name": forecast_payload["model_name"],
                "forecast_prices": forecast_payload["forecast_prices"],
                "history_prices": forecast_payload["history_prices"],
                "history_dates": forecast_payload["history_dates"],
                "forecast_dates": forecast_payload["forecast_dates"],
            },
        )

        return Response(
            {
                "forecast_id": forecast_obj.id,
                "forecast_type": forecast_type,
                "model_type": model_type,
                "horizon_days": horizon_days,
                "portfolio": {
                    "id": stock.portfolio.id,
                    "name": stock.portfolio.name,
                },
                "stock": {
                    "id": stock.id,
                    "ticker": stock.ticker,
                    "company_name": analysis.get("company_name") or stock.company_name,
                    "current_price": analysis.get("current_price") or stock.current_price,
                    "pe_ratio": analysis.get("pe_ratio"),
                    "high_52w": analysis.get("high_52w"),
                    "low_52w": analysis.get("low_52w"),
                    "market_cap": analysis.get("market_cap"),
                    "percent_from_low": analysis.get("percent_from_low"),
                    "percent_from_high": analysis.get("percent_from_high"),
                },
                "prediction": {
                    "model_name": forecast_payload["model_name"],
                    "model_order": forecast_payload["model_order"],
                    "predicted_price": forecast_payload["predicted_price"],
                    "predicted_for_date": forecast_payload["predicted_for_date"],
                    "forecast_prices": forecast_payload["forecast_prices"],
                    "forecast_dates": forecast_payload["forecast_dates"],
                    "confidence_interval_lower": forecast_payload["confidence_interval_lower"],
                    "confidence_interval_upper": forecast_payload["confidence_interval_upper"],
                },
                "graph": {
                    "history_prices": forecast_payload["history_prices"],
                    "history_dates": forecast_payload["history_dates"],
                    "fitted_prices": forecast_payload.get("fitted_prices") or [],
                    "fitted_dates": forecast_payload.get("fitted_dates") or [],
                    "forecast_prices": forecast_payload["forecast_prices"],
                    "forecast_dates": forecast_payload["forecast_dates"],
                },
            },
            status=200,
        )
