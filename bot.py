import logging
import os
import threading
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import ccxt
import pandas as pd
from dotenv import load_dotenv

import indicators
import storage
import strategy
from settings import Settings

load_dotenv()

testnet = os.getenv('BINANCE_TESTNET', 'true').lower() != 'false'

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


def bought_amount(order, coin):
    fee = sum(fee['cost'] for fee in order.get('fees') or [] if fee['currency'] == coin)
    return order['filled'] - fee


class Bot:
    def __init__(self, settings):
        self.settings = settings
        self.exchange = ccxt.binance({
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_API_SECRET'),
        })
        self.exchange.set_sandbox_mode(testnet)
        self.last_check = None
        self.stop_requested = threading.Event()
        self.thread = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            return
        self.stop_requested.clear()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_requested.set()

    def run(self):
        db = storage.connect()
        log.info(f'Starting on {"testnet" if testnet else "REAL ACCOUNT"} with {self.settings}')
        position = storage.get_position(db, self.settings.symbol, testnet)
        if position is not None:
            log.info(f'Open position: {position["amount"]} at {position["entry_price"]} since {position["opened_at"]}')
        while not self.stop_requested.is_set():
            self.trade(db)
            self.stop_requested.wait(self.seconds_until_next_candle())
        log.info('Stopped')

    def interval_ms(self):
        return self.exchange.parse_timeframe(self.settings.interval) * 1000

    def seconds_until_next_candle(self):
        now = self.exchange.milliseconds()
        return (self.interval_ms() - now % self.interval_ms()) / 1000 + 2

    def get_closes(self):
        candles = self.exchange.fetch_ohlcv(self.settings.symbol, self.settings.interval, limit=1000)
        now = self.exchange.milliseconds()
        closed = [candle for candle in candles if candle[0] + self.interval_ms() <= now]
        return pd.Series([candle[4] for candle in closed])

    def trade(self, db):
        settings = self.settings
        try:
            closes = self.get_closes()
            last_rsi = indicators.rsi(closes, settings.rsi_period).iloc[-1]
            last_trend = indicators.trend(closes, settings.trend_period).iloc[-1]
            self.last_check = {'time': datetime.now(), 'close': closes.iloc[-1], 'rsi': last_rsi, 'trend': last_trend}
            log.info(f'{settings.symbol} close: {closes.iloc[-1]} RSI: {last_rsi:.2f} trend: {last_trend:.2f}')

            coin = settings.symbol.split('/')[0]
            position = storage.get_position(db, settings.symbol, testnet)
            action = strategy.signal(last_rsi, closes.iloc[-1], last_trend, position is not None, settings)

            if action == 'buy':
                order = self.exchange.create_market_buy_order_with_cost(settings.symbol, settings.order_size_usdt)
                amount = bought_amount(order, coin)
                storage.record_buy(db, order, amount, testnet)
                log.info(f'BUY {amount} {coin} at {order["average"]} for {order["cost"]} USDT')

            if action == 'sell':
                available = position['amount'] + storage.get_leftover(db, settings.symbol, testnet)
                amount = self.exchange.amount_to_precision(settings.symbol, available)
                order = self.exchange.create_market_sell_order(settings.symbol, amount)
                leftover = max(available - order['filled'], 0.0)
                storage.record_sell(db, order, testnet, leftover)
                profit = order['cost'] - position['cost']
                log.info(f'SELL {amount} {coin} at {order["average"]} for {order["cost"]} USDT (P/L before fees: {profit:.4f} USDT, leftover kept: {leftover:.8f} {coin})')

        except Exception:
            log.exception('Error')


if __name__ == '__main__':
    setup_logging()
    Bot(Settings()).run()
