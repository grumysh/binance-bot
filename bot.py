import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import ccxt
from dotenv import load_dotenv

import storage
from settings import Settings

load_dotenv()

settings = Settings()
testnet = os.getenv('BINANCE_TESTNET', 'true').lower() != 'false'

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
})
exchange.set_sandbox_mode(testnet)

db = storage.connect()

log = logging.getLogger('bot')


def setup_logging():
    logs_dir = Path(__file__).parent / 'logs'
    logs_dir.mkdir(exist_ok=True)
    file_handler = TimedRotatingFileHandler(logs_dir / 'bot.log', when='midnight', backupCount=30, encoding='utf-8')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(), file_handler],
    )


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
    try:
        closes = get_closes()
        last_rsi = rsi(closes, settings.rsi_period)
        log.info(f'{settings.symbol} RSI: {last_rsi:.2f}')

        coin = settings.symbol.split('/')[0]
        position = storage.get_position(db, settings.symbol, testnet)

        if last_rsi < settings.rsi_buy_below and position is None:
            order = exchange.create_market_buy_order_with_cost(settings.symbol, settings.order_size_usdt)
            amount = bought_amount(order, coin)
            storage.record_buy(db, order, amount, testnet)
            log.info(f'BUY {amount} {coin} at {order["average"]} for {order["cost"]} USDT')

        if last_rsi > settings.rsi_sell_above and position is not None:
            amount = exchange.amount_to_precision(settings.symbol, position['amount'])
            order = exchange.create_market_sell_order(settings.symbol, amount)
            storage.record_sell(db, order, testnet)
            profit = order['cost'] - position['cost']
            log.info(f'SELL {amount} {coin} at {order["average"]} for {order["cost"]} USDT (P/L before fees: {profit:.4f} USDT)')

    except Exception:
        log.exception('Error')


if __name__ == '__main__':
    setup_logging()
    log.info(f'Starting on {"testnet" if testnet else "REAL ACCOUNT"} with {settings}')
    position = storage.get_position(db, settings.symbol, testnet)
    if position is not None:
        log.info(f'Open position: {position["amount"]} at {position["entry_price"]} since {position["opened_at"]}')
    while True:
        trade()
        wait_for_next_candle()
