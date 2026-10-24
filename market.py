import os
from datetime import datetime

import ccxt
import pandas as pd
from dotenv import load_dotenv

import indicators
import storage
import strategy

load_dotenv()

testnet = os.getenv('BINANCE_TESTNET', 'true').lower() != 'false'


def create_exchange():
    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
    })
    exchange.set_sandbox_mode(testnet)
    return exchange


CHART_CANDLES = 150


def fetch_candles(exchange, symbol, interval):
    candles = exchange.fetch_ohlcv(symbol, interval, limit=1000)
    interval_ms = exchange.parse_timeframe(interval) * 1000
    now = exchange.milliseconds()
    closed = [candle for candle in candles if candle[0] + interval_ms <= now]
    frame = pd.DataFrame(closed, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    frame.index = pd.to_datetime(frame.pop('time'), unit='ms', utc=True)
    return frame


def fetch_closes(exchange, symbol, interval):
    return fetch_candles(exchange, symbol, interval)['close']


def snapshot(exchange, settings):
    candles = fetch_candles(exchange, settings.symbol, settings.interval)
    closes = candles['close']
    candles = candles.assign(
        rsi=indicators.rsi(closes, settings.rsi_period),
        trend=indicators.trend(closes, settings.trend_period),
    )
    rsi = candles['rsi'].iloc[-1]
    trend = candles['trend'].iloc[-1]
    chart = candles.tail(CHART_CANDLES)
    price = exchange.fetch_ticker(settings.symbol)['last']
    balance = exchange.fetch_balance()['total']
    coin = settings.symbol.split('/')[0]

    db = storage.connect()
    position = storage.get_position(db, settings.symbol, testnet)
    trades = storage.get_trades(db, settings.symbol, testnet, chart.index[0].isoformat())
    if position is not None:
        position = dict(position)
        position['value'] = position['amount'] * price
        position['profit'] = position['value'] - position['cost']
        position['profit_percent'] = position['profit'] / position['cost'] * 100

    return {
        'time': datetime.now(),
        'coin': coin,
        'price': price,
        'last_close': closes.iloc[-1],
        'rsi': rsi,
        'trend': trend,
        'signal': strategy.signal(rsi, closes.iloc[-1], trend, position is not None, settings),
        'coin_balance': balance.get(coin, 0.0),
        'usdt_balance': balance.get('USDT', 0.0),
        'position': position,
        'chart': chart,
        'trades': [dict(trade) for trade in trades],
    }
