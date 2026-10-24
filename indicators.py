import pandas as pd


def wilder_average(values, period):
    smoothed = values.copy()
    smoothed.iloc[:period] = float('nan')
    smoothed.iloc[period] = values.iloc[1:period + 1].mean()
    return smoothed.ewm(alpha=1 / period, adjust=False).mean()


def rsi(closes, period=14):
    change = closes.diff()
    avg_gain = wilder_average(change.clip(lower=0), period)
    avg_loss = wilder_average(-change.clip(upper=0), period)
    value = 100 - 100 / (1 + avg_gain / avg_loss)
    return value.where(avg_loss != 0, 100.0).where(avg_gain.notna())


def candles_frame(rows):
    frame = pd.DataFrame([dict(row) for row in rows], columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    frame.index = pd.to_datetime(frame.pop('time'), unit='ms', utc=True)
    return frame
