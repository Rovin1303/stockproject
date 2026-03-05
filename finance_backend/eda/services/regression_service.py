from datetime import timedelta

import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from django.utils import timezone


def _clean_prices(price_history):
    cleaned_prices = []
    for value in price_history or []:
        try:
            cleaned_prices.append(float(value))
        except (TypeError, ValueError):
            continue

    # Use up to ~1 trading year of daily closes.
    return cleaned_prices[-252:]


def _build_features(prices, pe_ratio=None, market_cap=None):
    n = len(prices)
    if n < 40:
        return np.array([]), np.array([]), np.array([]), np.array([])

    X = []
    y_price = []
    y_direction = []

    pe_value = float(pe_ratio) if pe_ratio not in (None, "", 0) else 0.0
    market_cap_value = float(market_cap) if market_cap not in (None, "", 0) else 0.0
    pe_feature = np.log1p(max(pe_value, 0.0))
    market_cap_feature = np.log1p(max(market_cap_value, 0.0))

    for t in range(20, n - 1):
        close_t = prices[t]
        close_prev = prices[t - 1]
        close_5 = prices[t - 5]
        close_20 = prices[t - 20]
        next_close = prices[t + 1]

        if close_prev <= 0 or close_5 <= 0 or close_20 <= 0:
            continue

        window = np.array(prices[t - 19: t + 1], dtype=float)
        if window.size < 20:
            continue

        daily_returns = np.diff(window) / window[:-1]
        volatility_20 = float(np.std(daily_returns)) if daily_returns.size else 0.0
        sma_20 = float(np.mean(window)) if window.size else close_t
        sma_ratio_20 = (close_t / sma_20) if sma_20 else 1.0
        momentum_5 = (close_t / close_5) - 1.0
        momentum_20 = (close_t / close_20) - 1.0
        daily_return = (close_t / close_prev) - 1.0

        X.append(
            [
                close_t,
                daily_return,
                momentum_5,
                momentum_20,
                volatility_20,
                sma_ratio_20,
                pe_feature,
                market_cap_feature,
            ]
        )
        y_price.append(next_close)
        y_direction.append(1 if next_close >= close_t else 0)

    if not X:
        return np.array([]), np.array([]), np.array([]), np.array([])

    X = np.array(X, dtype=float)
    y_price = np.array(y_price, dtype=float)
    y_direction = np.array(y_direction, dtype=int)
    last_features = X[-1].reshape(1, -1)
    return X, y_price, y_direction, last_features


def predict_next_day_metrics(price_history, pe_ratio=None, market_cap=None):
    cleaned_prices = _clean_prices(price_history)
    if len(cleaned_prices) < 40:
        return None

    X, y_price, y_direction, last_features = _build_features(cleaned_prices, pe_ratio, market_cap)
    if X.size == 0:
        return None

    price_model = LinearRegression()
    price_model.fit(X, y_price)
    predicted_price = float(price_model.predict(last_features)[0])
    predicted_price = max(0.0, predicted_price)
    predicted_price = round(predicted_price, 2)

    if len(np.unique(y_direction)) > 1:
        direction_model = LogisticRegression(max_iter=1000)
        direction_model.fit(X, y_direction)
        up_probability = float(direction_model.predict_proba(last_features)[0][1])
    else:
        up_probability = 1.0 if y_direction[-1] == 1 else 0.0

    predicted_direction = "UP" if up_probability >= 0.5 else "DOWN"
    confidence = round(max(up_probability, 1 - up_probability) * 100, 2)

    return {
        "predicted_price": predicted_price,
        "predicted_direction": predicted_direction,
        "direction_confidence": confidence,
        "up_probability": round(up_probability, 4),
        "lookback_days": len(cleaned_prices),
    }


def predict_next_day_price(price_history, pe_ratio=None, market_cap=None):
    cleaned_prices = _clean_prices(price_history)[-30:]
    n = len(cleaned_prices)
    if n < 2:
        return None

    X = np.arange(n, dtype=float).reshape(-1, 1)
    y = np.array(cleaned_prices, dtype=float)

    model = LinearRegression()
    model.fit(X, y)

    prediction = float(model.predict(np.array([[n]], dtype=float))[0])
    prediction = max(0.0, prediction)
    return round(prediction, 2)


def predict_next_day_logistic_window(price_history, window_size=30):
    prices = _clean_prices(price_history)
    if len(prices) < (window_size + 2):
        return None

    prices_arr = np.array(prices, dtype=float)
    returns = (prices_arr[1:] / prices_arr[:-1]) - 1.0

    if returns.size <= window_size:
        return None

    X = []
    y = []
    for idx in range(window_size, returns.size):
        X.append(returns[idx - window_size:idx])
        y.append(1 if returns[idx] > 0 else 0)

    X = np.array(X, dtype=float)
    y = np.array(y, dtype=int)
    if X.size == 0:
        return None

    latest_window = returns[-window_size:].reshape(1, -1)

    if len(np.unique(y)) > 1:
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000),
        )
        model.fit(X, y)
        prob_up = float(model.predict_proba(latest_window)[0][1])
    else:
        prob_up = 1.0 if y[-1] == 1 else 0.0

    prob_down = 1.0 - prob_up
    predicted_class = 1 if prob_up >= 0.5 else 0

    return {
        "window_size": int(window_size),
        "samples": int(len(y)),
        "probability_up": round(prob_up, 4),
        "probability_down": round(prob_down, 4),
        "predicted_class": predicted_class,
        "predicted_label": "UP" if predicted_class == 1 else "DOWN",
    }


def tomorrow_date_str():
    tomorrow = timezone.localdate() + timedelta(days=1)
    return tomorrow.isoformat()
