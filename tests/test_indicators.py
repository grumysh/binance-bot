import random

import pandas as pd
import pytest

import indicators


def reference_rsi(closes, period):
    changes = [current - previous for previous, current in zip(closes, closes[1:])]
    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def test_rsi_matches_wilder_reference():
    generator = random.Random(1)
    closes = [100.0]
    for _ in range(300):
        closes.append(closes[-1] * (1 + generator.uniform(-0.02, 0.02)))
    for end in [20, 60, 150, 301]:
        window = closes[:end]
        assert indicators.rsi(pd.Series(window), 14).iloc[-1] == pytest.approx(reference_rsi(window, 14))


def test_rsi_needs_period_candles_before_its_first_value():
    values = indicators.rsi(pd.Series([float(i) for i in range(30)]), 14)
    assert values.iloc[:14].isna().all()
    assert values.iloc[14:].notna().all()


def test_rsi_is_100_without_losses():
    assert indicators.rsi(pd.Series([1.0] * 30)).iloc[-1] == 100
    assert indicators.rsi(pd.Series([float(i) for i in range(30)])).iloc[-1] == 100


def test_sma_and_trend():
    closes = pd.Series([1.0, 2.0, 3.0, 4.0])
    assert indicators.sma(closes, 2).tolist()[1:] == [1.5, 2.5, 3.5]
    assert indicators.trend(closes, 0).isna().all()
    assert indicators.trend(closes, 2).iloc[-1] == 3.5


def test_bollinger_bands_surround_the_average():
    closes = pd.Series([10.0, 12.0, 11.0, 13.0, 12.0, 14.0])
    lower, middle, upper = indicators.bollinger(closes, 4, 2)
    assert middle.iloc[-1] == pytest.approx(12.5)
    assert upper.iloc[-1] - middle.iloc[-1] == pytest.approx(middle.iloc[-1] - lower.iloc[-1])
    assert lower.iloc[-1] < closes.iloc[-4:].min()


def test_macd_is_zero_on_a_flat_price():
    line, signal = indicators.macd(pd.Series([5.0] * 50))
    assert line.abs().max() == 0
    assert signal.abs().max() == 0


def test_candles_frame_uses_utc_times():
    rows = [{'time': 0, 'open': 1, 'high': 2, 'low': 0.5, 'close': 1.5, 'volume': 3, 'symbol': 'BTC/USDT'}]
    frame = indicators.candles_frame(rows)
    assert list(frame.columns) == ['open', 'high', 'low', 'close', 'volume']
    assert str(frame.index[0]) == '1970-01-01 00:00:00+00:00'
