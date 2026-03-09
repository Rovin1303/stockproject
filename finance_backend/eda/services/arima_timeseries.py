from datetime import datetime, timedelta
import numpy as np


def _clean_prices(price_history):
    cleaned = []
    for value in price_history or []:
        try:
            cleaned.append(float(value))
        except (TypeError, ValueError):
            continue
    return cleaned


def _fallback_future_dates(last_date_str, horizon_days):
    try:
        start = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    except Exception:
        start = datetime.utcnow().date()

    out = []
    for i in range(1, horizon_days + 1):
        out.append((start + timedelta(days=i)).isoformat())
    return out


def _try_fit_arima(series):
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except Exception as exc:
        raise RuntimeError("statsmodels is required for ARIMA forecasting") from exc

    # Try slightly richer configuration first, then simpler fallbacks.
    candidate_orders = [(3, 1, 1), (2, 1, 1), (1, 1, 1), (1, 0, 0)]

    for order in candidate_orders:
        try:
            model = ARIMA(series, order=order)
            fitted = model.fit()
            return fitted, order
        except Exception:
            continue

    raise RuntimeError("Unable to fit ARIMA model for the selected stock history")


def _extract_confidence_bounds(conf_int_result, horizon_days):
    # statsmodels may return either a pandas DataFrame or a numpy array.
    if hasattr(conf_int_result, "iloc"):
        lower_vals = conf_int_result.iloc[:, 0].tolist()
        upper_vals = conf_int_result.iloc[:, 1].tolist()
    else:
        conf_arr = np.asarray(conf_int_result)
        if conf_arr.ndim != 2 or conf_arr.shape[1] < 2:
            raise RuntimeError("Invalid confidence interval data from ARIMA forecast")
        lower_vals = conf_arr[:, 0].tolist()
        upper_vals = conf_arr[:, 1].tolist()

    lower = [round(float(v), 2) for v in lower_vals][:horizon_days]
    upper = [round(float(v), 2) for v in upper_vals][:horizon_days]

    if len(lower) != horizon_days or len(upper) != horizon_days:
        raise RuntimeError("ARIMA confidence interval output length mismatch")

    return lower, upper


def predict_stock_timeseries(price_history, date_history, horizon_days):
    if horizon_days not in (1, 7):
        raise ValueError("horizon_days must be 1 or 7")

    prices = _clean_prices(price_history)
    if len(prices) < 25:
        raise ValueError("At least 25 daily prices are required for ARIMA forecasting")

    fitted_model, order = _try_fit_arima(prices)

    forecast_res = fitted_model.get_forecast(steps=horizon_days)
    forecast_values = [round(float(x), 2) for x in forecast_res.predicted_mean.tolist()]

    conf = forecast_res.conf_int(alpha=0.05)
    lower, upper = _extract_confidence_bounds(conf, horizon_days)

    history_dates = [str(d) for d in (date_history or [])][-len(prices):]
    last_date = history_dates[-1] if history_dates else None
    forecast_dates = _fallback_future_dates(last_date, horizon_days)

    return {
        "model_name": "ARIMA",
        "model_order": order,
        "history_prices": [round(float(v), 2) for v in prices],
        "history_dates": history_dates,
        "forecast_prices": forecast_values,
        "forecast_dates": forecast_dates,
        "confidence_interval_lower": lower,
        "confidence_interval_upper": upper,
        "predicted_price": forecast_values[-1],
        "predicted_for_date": forecast_dates[-1],
    }
