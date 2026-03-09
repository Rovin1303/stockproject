from datetime import datetime, timedelta
import math
import time
import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler


def _clean_prices(price_history):
    cleaned = []
    for value in price_history or []:
        try:
            cleaned.append(float(value))
        except (TypeError, ValueError):
            continue
    return cleaned


def _clean_feature(feature_history, fallback, n):
    out = []
    for i in range(n):
        raw = None
        if feature_history and i < len(feature_history):
            raw = feature_history[i]
        if raw is None:
            raw = fallback[i]
        try:
            out.append(float(raw))
        except (TypeError, ValueError):
            out.append(float(fallback[i]))
    return out


def _fallback_future_dates(last_date_str, horizon_days):
    try:
        start = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    except Exception:
        start = datetime.utcnow().date()

    out = []
    for i in range(1, horizon_days + 1):
        out.append((start + timedelta(days=i)).isoformat())
    return out


def _require_tensorflow():
    try:
        import importlib

        tf = importlib.import_module("tensorflow")
        keras = tf.keras
        Sequential = keras.Sequential
        LSTM = keras.layers.LSTM
        Bidirectional = keras.layers.Bidirectional
        Dense = keras.layers.Dense
        Dropout = keras.layers.Dropout
        Input = keras.layers.Input
        EarlyStopping = keras.callbacks.EarlyStopping
        ReduceLROnPlateau = keras.callbacks.ReduceLROnPlateau
        Huber = keras.losses.Huber
        Adam = keras.optimizers.Adam
    except Exception as exc:
        raise RuntimeError(
            "TensorFlow is required for RNN forecasting. Install tensorflow and retry."
        ) from exc

    return tf, Sequential, LSTM, Bidirectional, Dense, Dropout, Input, EarlyStopping, ReduceLROnPlateau, Huber, Adam


def _build_supervised_sequences(series, window_size):
    x, y = [], []
    for i in range(window_size, len(series)):
        x.append(series[i - window_size:i])
        y.append(series[i])

    if not x:
        return np.empty((0, window_size, 1)), np.empty((0, 1))

    x_arr = np.array(x, dtype=np.float32).reshape(-1, window_size, 1)
    y_arr = np.array(y, dtype=np.float32).reshape(-1, 1)
    return x_arr, y_arr


def _safe_returns(prices):
    ret = [0.0]
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        if abs(prev) < 1e-8:
            ret.append(0.0)
        else:
            ret.append((prices[i] - prev) / prev)
    return ret


def _moving_average(values, window):
    out = []
    rolling_sum = 0.0
    for i, v in enumerate(values):
        rolling_sum += v
        if i >= window:
            rolling_sum -= values[i - window]
        denom = window if i >= window - 1 else (i + 1)
        out.append(rolling_sum / denom)
    return out


def _rolling_std(values, window):
    out = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        segment = values[start:i + 1]
        out.append(float(np.std(np.array(segment, dtype=float))))
    return out


def _build_feature_matrix(price_history, date_history, open_history=None, high_history=None, low_history=None, volume_history=None):
    close = _clean_prices(price_history)
    if len(close) < 90:
        raise ValueError("At least 90 daily prices are required for LSTM forecasting")

    n = len(close)
    open_vals = _clean_feature(open_history, close, n)
    high_vals = _clean_feature(high_history, close, n)
    low_vals = _clean_feature(low_history, close, n)

    vol_fallback = [1.0] * n
    volume_vals = _clean_feature(volume_history, vol_fallback, n)

    # Ensure high/low consistency for noisy API rows.
    for i in range(n):
        hi = max(high_vals[i], open_vals[i], close[i], low_vals[i])
        lo = min(low_vals[i], open_vals[i], close[i], high_vals[i])
        high_vals[i] = hi
        low_vals[i] = lo
        if volume_vals[i] < 0:
            volume_vals[i] = abs(volume_vals[i])

    returns = _safe_returns(close)
    rolling_vol_20 = _rolling_std(returns, 20)
    ma10 = _moving_average(close, 10)
    ma20 = _moving_average(close, 20)

    dates = [str(d) for d in (date_history or [])][-n:]

    features = np.column_stack(
        [
            np.array(open_vals, dtype=np.float32),
            np.array(high_vals, dtype=np.float32),
            np.array(low_vals, dtype=np.float32),
            np.array(close, dtype=np.float32),
            np.array(volume_vals, dtype=np.float32),
            np.array(returns, dtype=np.float32),
            np.array(rolling_vol_20, dtype=np.float32),
            np.array(ma10, dtype=np.float32),
            np.array(ma20, dtype=np.float32),
        ]
    )
    return features, close, dates


def _fit_lstm_model(scaled_features, scaled_target, window_size):
    tf, Sequential, LSTM, Bidirectional, Dense, Dropout, Input, EarlyStopping, ReduceLROnPlateau, Huber, Adam = _require_tensorflow()
    tf.keras.utils.set_random_seed(42)

    x = []
    y = []
    for i in range(window_size, len(scaled_features)):
        x.append(scaled_features[i - window_size:i])
        y.append(scaled_target[i])

    if not x:
        raise ValueError("Not enough sequence data to train LSTM model")

    x = np.array(x, dtype=np.float32)
    y = np.array(y, dtype=np.float32).reshape(-1, 1)

    if len(x) < 28:
        raise ValueError("Not enough sequence data to train LSTM model")

    val_size = max(8, int(len(x) * 0.2))
    if len(x) - val_size < 10:
        val_size = max(4, len(x) // 5)

    if len(x) - val_size < 8:
        raise ValueError("Insufficient data to create train/validation split for LSTM")

    split_idx = len(x) - val_size
    x_train, y_train = x[:split_idx], y[:split_idx]
    x_val, y_val = x[split_idx:], y[split_idx:]

    n_features = int(scaled_features.shape[1])

    GaussianNoise = tf.keras.layers.GaussianNoise

    model = Sequential(
        [
            Input(shape=(window_size, n_features)),
            GaussianNoise(0.01),
            Bidirectional(LSTM(96, return_sequences=True,
                               kernel_regularizer=tf.keras.regularizers.l2(1e-4))),
            Dropout(0.3),
            Bidirectional(LSTM(48, return_sequences=False,
                               kernel_regularizer=tf.keras.regularizers.l2(1e-4))),
            Dropout(0.25),
            Dense(48, activation="relu"),
            Dense(1),
        ]
    )
    model.compile(optimizer=Adam(learning_rate=5e-4), loss=Huber())

    stop = EarlyStopping(
        monitor="val_loss",
        patience=18,
        restore_best_weights=True,
    )
    reduce_lr = ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=5,
        min_lr=1e-6,
    )

    class _TimeLimitCallback(tf.keras.callbacks.Callback):
        def __init__(self, max_seconds):
            super().__init__()
            self.max_seconds = max_seconds
            self.started_at = None

        def on_train_begin(self, logs=None):
            self.started_at = time.monotonic()

        def on_epoch_end(self, epoch, logs=None):
            if self.started_at is None:
                return
            if (time.monotonic() - self.started_at) >= self.max_seconds:
                self.model.stop_training = True

    max_train_seconds = 40
    time_limit = _TimeLimitCallback(max_seconds=max_train_seconds)

    history = model.fit(
        x_train,
        y_train,
        epochs=120,
        batch_size=24,
        validation_data=(x_val, y_val),
        shuffle=False,
        verbose=0,
        callbacks=[stop, reduce_lr, time_limit],
    )

    train_loss_series = history.history.get("loss") or []
    val_loss_series = history.history.get("val_loss") or []

    return model, x, y, {
        "epochs_trained": len(train_loss_series),
        "final_train_loss": float(train_loss_series[-1]) if train_loss_series else None,
        "best_val_loss": float(min(val_loss_series)) if val_loss_series else None,
        "train_samples": int(len(x_train)),
        "validation_samples": int(len(x_val)),
        "max_train_seconds": max_train_seconds,
    }


def _iterative_forecast(model, scaled_features, close_history, volume_history, window_size, horizon_days, feature_scaler, target_scaler):
    feature_window = np.array(scaled_features[-window_size:], dtype=np.float32)
    closes = list(close_history)
    volumes = list(volume_history)
    preds = []

    recent_returns = _safe_returns(closes)
    base_vol = float(np.std(np.array(recent_returns[-30:], dtype=float))) if len(recent_returns) > 4 else 0.01
    base_vol = min(max(base_vol, 0.003), 0.12)
    return_hist = list(recent_returns)

    for _ in range(horizon_days):
        x = feature_window.reshape(1, window_size, feature_window.shape[1])
        nxt_scaled_ret = float(model.predict(x, verbose=0)[0][0])
        # With StandardScaler, clip at ±3.5 standard deviations.
        nxt_scaled_ret = min(max(nxt_scaled_ret, -3.5), 3.5)

        nxt_ret = float(target_scaler.inverse_transform([[nxt_scaled_ret]])[0][0])
        prev_close = float(closes[-1])

        # Trust the model output directly — no mean-reversion adjustment
        # that would systematically fight trending markets.
        clipped_ret = min(max(nxt_ret, -8.0 * base_vol), 8.0 * base_vol)
        nxt_close = prev_close * (1.0 + clipped_ret)

        nxt_open = prev_close
        spread = abs(clipped_ret) * 0.65 + base_vol * 0.45
        nxt_high = max(nxt_open, nxt_close) * (1.0 + spread)
        nxt_low = min(nxt_open, nxt_close) * max(0.2, 1.0 - spread)

        vol_mean = float(np.mean(volumes[-20:])) if volumes else 1.0
        vol_amp = min(abs(clipped_ret) / max(base_vol, 1e-6), 2.2)
        nxt_volume = max(1.0, vol_mean * (1.0 + 0.35 * vol_amp))

        closes.append(float(nxt_close))
        volumes.append(float(nxt_volume))
        return_hist.append(float(clipped_ret))

        ma10 = float(np.mean(closes[-10:]))
        ma20 = float(np.mean(closes[-20:]))
        roll_vol = float(np.std(np.array(return_hist[-20:], dtype=float))) if return_hist else base_vol

        next_features = np.array(
            [[nxt_open, nxt_high, nxt_low, nxt_close, nxt_volume, clipped_ret, roll_vol, ma10, ma20]],
            dtype=np.float32,
        )
        next_features_scaled = feature_scaler.transform(next_features).astype(np.float32)

        feature_window = np.vstack([feature_window[1:], next_features_scaled])
        preds.append(round(float(nxt_close), 2))

    return preds


def _confidence_bands(prices, forecast_values, residual_std=None):
    if len(prices) < 3 and residual_std is None:
        lower = [round(v * 0.98, 2) for v in forecast_values]
        upper = [round(v * 1.02, 2) for v in forecast_values]
        return lower, upper

    arr = np.array(prices, dtype=float)
    returns = []
    for i in range(1, len(arr)):
        prev = arr[i - 1]
        if prev:
            returns.append((arr[i] - prev) / prev)

    if not returns:
        lower = [round(v * 0.98, 2) for v in forecast_values]
        upper = [round(v * 1.02, 2) for v in forecast_values]
        return lower, upper

    return_vol = float(np.std(np.array(returns[-30:], dtype=float))) if returns else 0.01
    return_vol = min(max(return_vol, 0.003), 0.12)

    if residual_std is not None and residual_std > 0:
        # residual_std is expected to be a relative error std (e.g. 0.01 == 1%).
        sigma = 0.6 * float(residual_std) + 0.4 * return_vol
    else:
        sigma = return_vol

    # Guard against unstable training causing unrealistic uncertainty explosions.
    sigma = min(max(sigma, 0.003), 0.15)

    z = 1.96

    lower = []
    upper = []
    for i, val in enumerate(forecast_values, start=1):
        band = abs(val) * z * sigma * math.sqrt(i)
        lower.append(round(val - band, 2))
        upper.append(round(val + band, 2))

    return lower, upper


def predict_stock_timeseries_rnn(
    price_history,
    date_history,
    horizon_days,
    open_history=None,
    high_history=None,
    low_history=None,
    volume_history=None,
):
    if horizon_days not in (1, 7):
        raise ValueError("horizon_days must be 1 or 7")

    features, prices, history_dates = _build_feature_matrix(
        price_history=price_history,
        date_history=date_history,
        open_history=open_history,
        high_history=high_history,
        low_history=low_history,
        volume_history=volume_history,
    )

    # Bound training cost in request/response flow by limiting sequence length.
    max_points = 300
    features = features[-max_points:]
    prices = prices[-max_points:]
    history_dates = history_dates[-max_points:]
    if len(prices) < 90:
        raise ValueError("At least 90 daily prices are required for LSTM forecasting")

    # Near-constant series can make LSTM unstable and produce noisy outputs.
    if max(prices) - min(prices) < 1e-6:
        history_dates = [str(d) for d in (date_history or [])][-len(prices):]
        last_date = history_dates[-1] if history_dates else None
        forecast_dates = _fallback_future_dates(last_date, horizon_days)
        baseline = round(float(prices[-1]), 2)
        lower = [round(baseline * 0.995, 2) for _ in range(horizon_days)]
        upper = [round(baseline * 1.005, 2) for _ in range(horizon_days)]
        forecast_values = [baseline for _ in range(horizon_days)]

        return {
            "model_name": "LSTM",
            "model_order": {
                "window_size": None,
                "layers": [],
                "framework": "tensorflow",
                "fallback": "constant_series",
            },
            "history_prices": [round(float(v), 2) for v in prices],
            "history_dates": history_dates,
            "forecast_prices": forecast_values,
            "forecast_dates": forecast_dates,
            "confidence_interval_lower": lower,
            "confidence_interval_upper": upper,
            "predicted_price": forecast_values[-1],
            "predicted_for_date": forecast_dates[-1],
        }

    window_size = 90

    feature_scaler = MinMaxScaler(feature_range=(0, 1))
    target_scaler = StandardScaler()

    scaled_features = feature_scaler.fit_transform(features).astype(np.float32)
    returns = np.array(_safe_returns(prices), dtype=np.float32)
    scaled_target = target_scaler.fit_transform(returns.reshape(-1, 1)).flatten()

    model, train_x, train_y, train_meta = _fit_lstm_model(scaled_features, scaled_target, window_size)

    # Residual std from in-sample predictions helps provide more realistic bands.
    train_pred_scaled = model.predict(train_x, verbose=0).flatten()
    train_true_ret = target_scaler.inverse_transform(train_y).flatten()
    train_pred_ret = target_scaler.inverse_transform(train_pred_scaled.reshape(-1, 1)).flatten()

    # Convert residuals to relative error so confidence math stays on return scale.
    if len(train_true_ret):
        residual_returns = train_true_ret - train_pred_ret
        residual_std = float(np.std(residual_returns))
    else:
        residual_std = None

    fit_dates = history_dates[window_size:]
    fitted_prices = []
    for i, pred_r in enumerate(train_pred_ret, start=window_size):
        prev_price = prices[i - 1]
        fitted_prices.append(round(float(prev_price * (1.0 + float(pred_r))), 2))

    forecast_values = _iterative_forecast(
        model=model,
        scaled_features=scaled_features,
        close_history=prices,
        volume_history=features[:, 4].tolist(),
        window_size=window_size,
        horizon_days=horizon_days,
        feature_scaler=feature_scaler,
        target_scaler=target_scaler,
    )
    lower, upper = _confidence_bands(prices, forecast_values, residual_std=residual_std)

    last_date = history_dates[-1] if history_dates else None
    forecast_dates = _fallback_future_dates(last_date, horizon_days)

    return {
        "model_name": "LSTM",
        "model_order": {
            "window_size": window_size,
            "layers": ["BiLSTM96", "BiLSTM48"],
            "framework": "tensorflow",
            "loss": "huber",
            "optimizer": "adam",
            "learning_rate": 5e-4,
            "features": ["open", "high", "low", "close", "volume", "returns", "rolling_volatility_20", "ma10", "ma20"],
            "target": "next_return",
            "forecasting_mode": "walk_forward_recursive",
            "training": train_meta,
        },
        "history_prices": [round(float(v), 2) for v in prices],
        "history_dates": history_dates,
        "fitted_prices": fitted_prices,
        "fitted_dates": fit_dates,
        "forecast_prices": forecast_values,
        "forecast_dates": forecast_dates,
        "confidence_interval_lower": lower,
        "confidence_interval_upper": upper,
        "predicted_price": forecast_values[-1],
        "predicted_for_date": forecast_dates[-1],
    }
