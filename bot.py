import os
import time

import ccxt
from dotenv import load_dotenv

load_dotenv()

SYMBOL = 'XAI/USDT'
INTERVAL = '1m'
RSI_PERIOD = 14
ORDER_SIZE_USDT = 10

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
})
exchange.set_sandbox_mode(os.getenv('BINANCE_TESTNET', 'true').lower() != 'false')

in_position = False


def get_closes():
    candles = exchange.fetch_ohlcv(SYMBOL, INTERVAL, limit=100)
    return [candle[4] for candle in candles]


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


def trade():
    global in_position
    try:
        closes = get_closes()
        last_rsi = rsi(closes, RSI_PERIOD)
        print(f'RSI: {last_rsi:.2f}')

        if last_rsi < 30 and not in_position:
            print('BUYING...')
            exchange.create_market_buy_order_with_cost(SYMBOL, ORDER_SIZE_USDT)
            in_position = True

        if last_rsi > 70 and in_position:
            print('SELLING...')
            asset = SYMBOL.split('/')[0]
            qty = exchange.fetch_balance()['free'].get(asset, 0)
            if qty > 0:
                exchange.create_market_sell_order(SYMBOL, exchange.amount_to_precision(SYMBOL, qty))
                in_position = False

    except Exception as err:
        print('Error:', err)


if __name__ == '__main__':
    while True:
        trade()
        time.sleep(60)
