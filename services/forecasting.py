
from datetime import timedelta

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error


AVAILABLE_MODELS = [
    "Moving Average",
    "Weighted Moving Average",
    "Exponential Smoothing",
    "Linear Regression",
    "Random Forest",
    "Seasonal Naive",
]


def _create_features(dates, start_index=0):
    dates = pd.DatetimeIndex(dates)

    return pd.DataFrame({
        "t": np.arange(start_index, start_index + len(dates)),
        "dow": dates.dayofweek,
        "month": dates.month,
        "day": dates.day,
        "week": dates.isocalendar().week.astype(int).to_numpy(),
    })


def _predict(history_values, history_dates, future_dates, model_name):
    values = np.asarray(history_values, dtype=float)
    steps = len(future_dates)

    if model_name == "Moving Average":
        window = min(7, len(values))
        prediction = np.repeat(np.mean(values[-window:]), steps)

    elif model_name == "Weighted Moving Average":
        window = min(7, len(values))
        recent = values[-window:]
        weights = np.arange(1, window + 1, dtype=float)
        average = np.average(recent, weights=weights)
        prediction = np.repeat(average, steps)

    elif model_name == "Exponential Smoothing":
        alpha = 0.30
        level = values[0]

        for value in values[1:]:
            level = alpha * value + (1 - alpha) * level

        prediction = np.repeat(level, steps)

    elif model_name == "Seasonal Naive":
        weekly_pattern = values[-min(7, len(values)):]
        prediction = np.resize(weekly_pattern, steps)

    elif model_name in ("Linear Regression", "Random Forest"):
        X_train = _create_features(history_dates)
        X_future = _create_features(
            future_dates,
            start_index=len(values)
        )

        if model_name == "Linear Regression":
            model = LinearRegression()
        else:
            model = RandomForestRegressor(
                n_estimators=150,
                random_state=42,
                min_samples_leaf=2
            )

        model.fit(X_train, values)
        prediction = model.predict(X_future)

    else:
        raise ValueError("Unknown forecasting model.")

    return np.maximum(0, prediction)


def forecast_product(history, model_name, horizon):

    if horizon not in (7, 15, 30, 90):
        raise ValueError(
            "Choose a forecast period of 7, 15, 30 or 90 days."
        )

    if model_name not in AVAILABLE_MODELS:
        raise ValueError("Please select a valid forecasting model.")

    if history is None or history.empty:
        raise ValueError("No historical sales data is available.")

    df = history.copy()

    df["sale_date"] = pd.to_datetime(df["sale_date"])
    df["quantity"] = pd.to_numeric(
        df["quantity"], errors="coerce"
    )

    df = df.dropna(subset=["sale_date", "quantity"])

    if df.empty:
        raise ValueError("No valid sales records are available.")

    daily = (
        df.groupby("sale_date")["quantity"]
        .sum()
        .sort_index()
    )

    daily = daily.asfreq("D", fill_value=0).astype(float)

    if len(daily) < 7:
        raise ValueError(
            "At least 7 days of historical data are required."
        )

    values = daily.to_numpy()
    dates = daily.index

    # Validate the model using the most recent historical observations.
    
    # Validate only when enough history is available.
    mae = None
    rmse = None
    mape = None

    if len(values) >= 14:

        validation_size = min(
            max(7, int(np.ceil(len(values) * 0.20))),
            len(values) - 7
        )

        train_values = values[:-validation_size]
        train_dates = dates[:-validation_size]

        test_dates = dates[-validation_size:]
        test_actual = values[-validation_size:]

        test_predictions = _predict(
            train_values,
            train_dates,
            test_dates,
            model_name
        )

        mae = float(
            mean_absolute_error(test_actual, test_predictions)
        )

        rmse = float(
            np.sqrt(
                mean_squared_error(test_actual, test_predictions)
            )
        )

        nonzero = test_actual != 0

        if np.any(nonzero):
            mape = float(
                np.mean(
                    np.abs(
                        (test_actual[nonzero] - test_predictions[nonzero])
                        / test_actual[nonzero]
                    )
                ) * 100
            )

    # Generate the final forecast using all available history.
    future_dates = pd.date_range(
        start=dates[-1] + timedelta(days=1),
        periods=horizon,
        freq="D"
    )

    predictions = _predict(
        values,
        dates,
        future_dates,
        model_name
    )

    rows = [
        {
            "date": date.strftime("%Y-%m-%d"),
            "prediction": round(float(prediction), 2)
        }
        for date, prediction in zip(future_dates, predictions)
    ]

    return {
        "rows": rows,
        "dates": [
            date.strftime("%Y-%m-%d")
            for date in dates[-30:]
        ],
        "actual": [
            round(float(value), 2)
            for value in values[-30:]
        ],
        "forecast_dates": [
            row["date"] for row in rows
        ],
        "forecast_values": [
            row["prediction"] for row in rows
        ],
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2) if mape is not None else None
    }
