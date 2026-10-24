import os
import time

import ccxt
from dotenv import load_dotenv

from settings import Settings

load_dotenv()

settings = Settings()

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
})
exchange.set_sandbox_mode(os.getenv('BINANCE_TESTNET', 'true').lower() != 'false')

position_amount = 0.0


def interval_ms():
    return exchange.parse_timeframe(settings.interval) * 1000


def get_closes():
    candles = exchange.fetch_ohlcv(settings.symbol, settings.interval, limit=100)
    now = exchange.milliseconds()
    closed = [candle for candle in candles if candle[0] + interval_ms() <= now]
    return [candle[4] for candle in closed]


def wait_for_next_candle():
    now = exchange.milliseconds()
    time.sleep((interval_ms() - now % interval_ms()) / 1000 + 2)


def rsi(closes, period):
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


def bought_amount(order, coin):
    fee = sum(fee['cost'] for fee in order.get('fees') or [] if fee['currency'] == coin)
    return order['filled'] - fee


def trade():
    global position_amount
    try:
        closes = get_closes()
        last_rsi = rsi(closes, settings.rsi_period)
        print(f'{settings.symbol} RSI: {last_rsi:.2f}')

        coin = settings.symbol.split('/')[0]

        if last_rsi < settings.rsi_buy_below and position_amount == 0:
            print('BUYING...')
            order = exchange.create_market_buy_order_with_cost(settings.symbol, settings.order_size_usdt)
            position_amount = bought_amount(order, coin)
            print(f'Bought {position_amount} {coin}')

        if last_rsi > settings.rsi_sell_above and position_amount > 0:
            print('SELLING...')
            amount = exchange.amount_to_precision(settings.symbol, position_amount)
            exchange.create_market_sell_order(settings.symbol, amount)
            print(f'Sold {amount} {coin}')
            position_amount = 0.0

    except Exception as err:
        print('Error:', err)


if __name__ == '__main__':
    while True:
        trade()
        wait_for_next_candle()
