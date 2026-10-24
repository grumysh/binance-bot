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


def fetch_closes(exchange, symbol, interval):
    candles = exchange.fetch_ohlcv(symbol, interval, limit=1000)
    interval_ms = exchange.parse_timeframe(interval) * 1000
    now = exchange.milliseconds()
    closed = [candle for candle in candles if candle[0] + interval_ms <= now]
    return pd.Series([candle[4] for candle in closed])


def snapshot(exchange, settings):
    closes = fetch_closes(exchange, settings.symbol, settings.interval)
    rsi = indicators.rsi(closes, settings.rsi_period).iloc[-1]
    trend = indicators.trend(closes, settings.trend_period).iloc[-1]
    price = exchange.fetch_ticker(settings.symbol)['last']
    balance = exchange.fetch_balance()['total']
    coin = settings.symbol.split('/')[0]

    position = storage.get_position(storage.connect(), settings.symbol, testnet)
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
    }
