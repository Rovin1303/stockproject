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

    # When modeling returns, differencing is already applied, so keep d=0.
    candidate_orders = [(4, 0, 2), (3, 0, 2), (2, 0, 2), (2, 0, 1), (1, 0, 1)]

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


def _build_price_forecast_from_returns(last_price, return_forecast):
    out = []
    current = float(last_price)
    for r in return_forecast:
        current = current * float(np.exp(r))
        out.append(round(float(current), 2))
    return out


def _confidence_prices_from_return_bounds(last_price, lower_returns, upper_returns):
    lower = []
    upper = []
    cur_low = float(last_price)
    cur_high = float(last_price)
    for lo_r, hi_r in zip(lower_returns, upper_returns):
        cur_low = cur_low * float(np.exp(lo_r))
        cur_high = cur_high * float(np.exp(hi_r))
        lower.append(round(float(cur_low), 2))
        upper.append(round(float(cur_high), 2))
    return lower, upper


def predict_stock_timeseries(price_history, date_history, horizon_days):
    if horizon_days not in (1, 7):
        raise ValueError("horizon_days must be 1 or 7")

    prices = _clean_prices(price_history)
    if len(prices) < 40:
        raise ValueError("At least 40 daily prices are required for ARIMA forecasting")

    # Use log-returns to avoid overly flat level forecasts while keeping pure ARIMA.
    clipped_prices = np.maximum(np.array(prices, dtype=np.float64), 1e-8)
    log_prices = np.log(clipped_prices)
    log_returns = np.diff(log_prices)

    if len(log_returns) < 20:
        raise ValueError("Insufficient data after preprocessing for ARIMA forecasting")

    fitted_model, order = _try_fit_arima(log_returns)

    forecast_res = fitted_model.get_forecast(steps=horizon_days)
    forecast_returns = [float(x) for x in forecast_res.predicted_mean.tolist()]
    forecast_values = _build_price_forecast_from_returns(prices[-1], forecast_returns)

    conf = forecast_res.conf_int(alpha=0.05)
    lower_ret, upper_ret = _extract_confidence_bounds(conf, horizon_days)
    lower, upper = _confidence_prices_from_return_bounds(prices[-1], lower_ret, upper_ret)

    fitted_returns = np.asarray(fitted_model.fittedvalues, dtype=float)
    fitted_prices = []
    for idx, r in enumerate(fitted_returns, start=1):
        prev_price = prices[idx - 1]
        fitted_prices.append(round(float(prev_price * float(np.exp(r))), 2))

    history_dates = [str(d) for d in (date_history or [])][-len(prices):]
    fitted_dates = history_dates[1:1 + len(fitted_prices)]
    last_date = history_dates[-1] if history_dates else None
    forecast_dates = _fallback_future_dates(last_date, horizon_days)

    return {
        "model_name": "ARIMA",
        "model_order": {
            "order": order,
            "series": "log_returns",
        },
        "history_prices": [round(float(v), 2) for v in prices],
        "history_dates": history_dates,
        "fitted_prices": fitted_prices,
        "fitted_dates": fitted_dates,
        "forecast_prices": forecast_values,
        "forecast_dates": forecast_dates,
        "confidence_interval_lower": lower,
        "confidence_interval_upper": upper,
        "predicted_price": forecast_values[-1],
        "predicted_for_date": forecast_dates[-1],
    }
