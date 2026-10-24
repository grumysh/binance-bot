import sys
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import storage

pytest_plugins = ['nicegui.testing.user_plugin']

STEPS = {'BTC/USDT': '0.00001', 'ETH/USDT': '0.0001'}


class FakeExchange:
    def __init__(self, candles=None):
        self.candles = candles
        self.orders = []
        self.now = None

    def load_markets(self):
        return {}

    def amount_to_precision(self, symbol, amount):
        return str(Decimal(str(amount)).quantize(Decimal(STEPS[symbol]), rounding=ROUND_DOWN))

    def parse_timeframe(self, interval):
        return pd.Timedelta(interval.replace('m', 'min')).total_seconds()

    def milliseconds(self):
        return self.now if self.now is not None else int(pd.Timestamp.now(tz='UTC').timestamp() * 1000)

    def iso8601(self, milliseconds):
        return pd.Timestamp(milliseconds, unit='ms', tz='UTC').isoformat()

    def fetch_ohlcv(self, symbol, interval, limit=1000, since=None):
        return self.candles[-limit:]

    def order(self, symbol, side, amount, price, fee=0.0, fee_currency=None):
        order = {
            'id': str(len(self.orders) + 1),
            'symbol': symbol,
            'side': side,
            'datetime': pd.Timestamp.now(tz='UTC').isoformat(),
            'filled': amount,
            'average': price,
            'cost': amount * price,
            'fees': [{'cost': fee, 'currency': fee_currency}] if fee_currency else [],
        }
        self.orders.append(order)
        return order

    def create_market_buy_order_with_cost(self, symbol, cost):
        price = self.candles[-1][4]
        amount = float(self.amount_to_precision(symbol, cost / price))
        return self.order(symbol, 'buy', amount, price, fee=amount * 0.001, fee_currency=symbol.split('/')[0])

    def create_market_sell_order(self, symbol, amount):
        price = self.candles[-1][4]
        amount = float(amount)
        return self.order(symbol, 'sell', amount, price, fee=amount * price * 0.001, fee_currency='USDT')


def make_candles(closes, interval='1h', start='2026-01-01'):
    times = pd.date_range(start, periods=len(closes), freq=interval.replace('m', 'min'), tz='UTC')
    opens = [closes[0], *closes[:-1]]
    frame = pd.DataFrame({
        'open': opens,
        'high': [max(o, c) for o, c in zip(opens, closes)],
        'low': [min(o, c) for o, c in zip(opens, closes)],
        'close': closes,
        'volume': [1.0] * len(closes),
    }, index=times)
    frame.index.name = 'time'
    return frame


def as_ohlcv(frame):
    return [
        [int(time.timestamp() * 1000), row.open, row.high, row.low, row.close, row.volume]
        for time, row in zip(frame.index, frame.itertuples())
    ]


def dip_and_recovery(start=80000.0):
    flat = [start + (50 if i % 2 else -50) for i in range(30)]
    falling = [flat[-1] * (1 - 0.01 * (i + 1)) for i in range(15)]
    rising = [falling[-1] * (1 + 0.012 * (i + 1)) for i in range(25)]
    return flat + falling + rising


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'test.db')
    return storage.connect()
