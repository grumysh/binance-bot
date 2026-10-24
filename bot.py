import logging
import threading
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import market
import notifier
import storage
import strategy
from journal import journal, today_profit
from market import testnet
from settings import Settings

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


def load_settings():
    data = storage.load_settings(storage.connect())
    if data:
        try:
            return Settings.from_dict(data)
        except ValueError:
            log.warning('Saved settings are not valid anymore, using the defaults')
    return Settings()


def bought_amount(order, coin):
    fee = sum(fee['cost'] for fee in order.get('fees') or [] if fee['currency'] == coin)
    return order['filled'] - fee


class Bot:
    def __init__(self, settings):
        self.settings = settings
        self.exchange = market.create_exchange()
        self.last_check = None
        self.last_error = None
        self.limit_notified_on = None
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
        settings = self.settings
        log.info(f'Starting on {"testnet" if testnet else "REAL ACCOUNT"} with {settings}')
        message = f'Bot started: {settings.symbol} {settings.interval} {strategy.name(settings)}'
        position = storage.get_position(db, settings.symbol, testnet)
        if position is not None:
            log.info(f'Open position: {position["amount"]} at {position["entry_price"]} since {position["opened_at"]}')
            message += f', open position of {position["amount"]} bought at {position["entry_price"]}'
        notifier.send(message)
        while not self.stop_requested.is_set():
            self.trade(db)
            self.stop_requested.wait(self.seconds_until_next_candle())
        log.info('Stopped')
        notifier.send('Bot stopped')

    def interval_ms(self):
        return self.exchange.parse_timeframe(self.settings.interval) * 1000

    def seconds_until_next_candle(self):
        now = self.exchange.milliseconds()
        return (self.interval_ms() - now % self.interval_ms()) / 1000 + 2

    def trade(self, db):
        settings = self.settings
        try:
            candles = market.fetch_candles(self.exchange, settings.symbol, settings.interval)
            candles = strategy.add_indicators(candles, settings)
            current, previous = candles.iloc[-1], candles.iloc[-2]
            indicators_text = strategy.describe(current, settings)
            self.last_check = {
                'time': datetime.now(),
                'close': current['close'],
                'indicators': indicators_text,
                'trend': current['trend'],
            }
            log.info(f'{settings.symbol} close: {current["close"]} {indicators_text} trend: {current["trend"]:.2f}')

            coin = settings.symbol.split('/')[0]
            position = storage.get_position(db, settings.symbol, testnet)
            entry_price = position['entry_price'] if position is not None else None
            action = strategy.signal(current, previous, entry_price, settings)
            if action == 'buy':
                profit_today = today_profit(journal(storage.get_all_trades(db, testnet)))
                if strategy.daily_limit_reached(profit_today, settings):
                    action = None
                    message = (
                        f'Daily loss limit reached ({profit_today:+.2f} USDT today, limit '
                        f'{settings.daily_loss_limit_usdt:g} USDT). No new buys until tomorrow.'
                    )
                    log.info(message)
                    if self.limit_notified_on != datetime.now().date():
                        self.limit_notified_on = datetime.now().date()
                        notifier.send(message)

            if action == 'buy':
                order = self.exchange.create_market_buy_order_with_cost(settings.symbol, settings.order_size_usdt)
                amount = bought_amount(order, coin)
                storage.record_buy(db, order, amount, testnet)
                message = f'BUY {amount} {coin} at {order["average"]} for {order["cost"]} USDT'
                log.info(message)
                notifier.send(message)

            if action in ('sell', 'stop_loss'):
                available = position['amount'] + storage.get_leftover(db, settings.symbol, testnet)
                amount = self.exchange.amount_to_precision(settings.symbol, available)
                order = self.exchange.create_market_sell_order(settings.symbol, amount)
                leftover = max(available - order['filled'], 0.0)
                storage.record_sell(db, order, testnet, leftover)
                profit = order['cost'] - order['filled'] * position['entry_price']
                reason = 'STOP LOSS' if action == 'stop_loss' else 'SELL'
                log.info(f'{reason} {amount} {coin} at {order["average"]} for {order["cost"]} USDT (P/L before fees: {profit:.4f} USDT, leftover kept: {leftover:.8f} {coin})')
                notifier.send(f'{reason} {amount} {coin} at {order["average"]} for {order["cost"]} USDT, P/L before fees {profit:+.4f} USDT')

            self.last_error = None

        except Exception as error:
            log.exception('Error')
            if str(error) != self.last_error:
                self.last_error = str(error)
                notifier.send(f'Error: {error}')


if __name__ == '__main__':
    setup_logging()
    settings = load_settings()
    if not testnet:
        print(f'REAL ACCOUNT: {settings.symbol} {settings.interval} {strategy.name(settings)}, '
              f'{settings.order_size_usdt:g} USDT per trade.')
        if input('Type REAL to trade with real money: ').strip() != 'REAL':
            raise SystemExit('Not started.')
    Bot(settings).run()
