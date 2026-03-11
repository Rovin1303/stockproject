from datetime import datetime, timedelta
import numpy as np


def _clean_prices(price_history):
    out = []
    for value in price_history or []:
        try:
            out.append(float(value))
        except (TypeError, ValueError):
            continue
    return out


def _future_dates(last_date_str, horizon_days):
    try:
        start = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    except Exception:
        start = datetime.utcnow().date()

    return [(start + timedelta(days=i)).isoformat() for i in range(1, horizon_days + 1)]


def _fit_best_arima(series):
    try:
        from statsmodels.tsa.arima.model import ARIMA
    except Exception as exc:
        raise RuntimeError("statsmodels is required for ARIMA forecasting") from exc

    best_fit = None
    best_order = None
    best_aic = np.inf

    # We model log-returns, so d=0. Keep grid compact for speed and stability.
    for order in ((1, 0, 1), (2, 0, 1), (2, 0, 2), (3, 0, 1), (3, 0, 2)):
        try:
            model = ARIMA(
                series,
                order=order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            fitted = model.fit()
            aic = float(getattr(fitted, "aic", np.inf))
            if aic < best_aic:
                best_fit = fitted
                best_order = order
                best_aic = aic
        except Exception:
            continue

    if best_fit is not None:
        return best_fit, best_order

    raise RuntimeError("Unable to fit ARIMA model for the selected stock history")


def _compound_prices(last_price, return_series):
    prices = []
    current = float(last_price)
    for value in return_series:
        current *= float(np.exp(float(value)))
        prices.append(round(current, 2))
    return prices


def _one_step_fitted_prices(actual_prices, fitted_returns):
    # For in-sample fit visualization, use previous actual close so the fitted
    # line reflects one-step-ahead predictions at each timestamp.
    out = []
    max_len = min(len(fitted_returns), len(actual_prices) - 1)
    for i in range(max_len):
        prev_price = float(actual_prices[i])
        out.append(round(prev_price * float(np.exp(float(fitted_returns[i]))), 2))
    return out


def predict_stock_timeseries(price_history, date_history, horizon_days):
    if horizon_days not in (1, 7):
        raise ValueError("horizon_days must be 1 or 7")

    prices = _clean_prices(price_history)
    if len(prices) < 40:
        raise ValueError("At least 40 daily prices are required for ARIMA forecasting")

    clipped_prices = np.maximum(np.array(prices, dtype=np.float64), 1e-8)
    log_prices = np.log(clipped_prices)
    log_returns = np.diff(log_prices).astype(np.float64)

    if len(log_returns) < 20:
        raise ValueError("Insufficient data after preprocessing for ARIMA forecasting")

    # Light outlier clipping improves stability without over-smoothing trends.
    ret_mean = float(np.mean(log_returns))
    ret_std = float(np.std(log_returns))
    if ret_std > 0:
        low = ret_mean - 4.0 * ret_std
        high = ret_mean + 4.0 * ret_std
        log_returns = np.clip(log_returns, low, high)

    fitted_model, order = _fit_best_arima(log_returns)

    forecast_res = fitted_model.get_forecast(steps=horizon_days)
    forecast_returns = np.asarray(forecast_res.predicted_mean, dtype=float)
    forecast_values = _compound_prices(prices[-1], forecast_returns)

    conf = forecast_res.conf_int(alpha=0.05)
    conf_arr = conf.values if hasattr(conf, "values") else np.asarray(conf, dtype=float)
    if conf_arr.ndim != 2 or conf_arr.shape[1] < 2:
        raise RuntimeError("Invalid confidence interval data from ARIMA forecast")
    lower = _compound_prices(prices[-1], conf_arr[:horizon_days, 0])
    upper = _compound_prices(prices[-1], conf_arr[:horizon_days, 1])

    fitted_returns = np.asarray(fitted_model.fittedvalues, dtype=float)
    fit_len = min(len(fitted_returns), len(prices) - 1)
    fitted_prices = _one_step_fitted_prices(prices, fitted_returns[:fit_len])

    history_dates = [str(d) for d in (date_history or [])][-len(prices):]
    fitted_dates = history_dates[1:1 + fit_len]
    last_date = history_dates[-1] if history_dates else None
    forecast_dates = _future_dates(last_date, horizon_days)

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
