import argparse

import ccxt

import storage
from settings import SYMBOLS, Settings

DAY_MS = 24 * 60 * 60 * 1000

exchange = ccxt.binance()


def download_candles(db, symbol, interval, days):
    interval_ms = exchange.parse_timeframe(interval) * 1000
    now = exchange.milliseconds()
    since = now - days * DAY_MS
    first_time, last_time = storage.candle_range(db, symbol, interval)
    if first_time is not None and first_time <= since <= last_time:
        since = last_time + interval_ms

    total = 0
    while since < now - interval_ms:
        candles = exchange.fetch_ohlcv(symbol, interval, since=since, limit=1000)
        closed = [candle for candle in candles if candle[0] + interval_ms <= now]
        if not closed:
            break
        storage.save_candles(db, symbol, interval, closed)
        total += len(closed)
        since = closed[-1][0] + interval_ms
        print(f'{symbol} {interval}: {total} candles, up to {exchange.iso8601(closed[-1][0])}')
    return total


if __name__ == '__main__':
    defaults = Settings()
    parser = argparse.ArgumentParser(description='Download historical candles from Binance into bot.db')
    parser.add_argument('--symbol', default=defaults.symbol, choices=SYMBOLS)
    parser.add_argument('--interval', default=defaults.interval)
    parser.add_argument('--days', type=int, default=30)
    args = parser.parse_args()

    download_candles(storage.connect(), args.symbol, args.interval, args.days)
