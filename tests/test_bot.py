from dataclasses import replace

import pytest

import bot
import storage
import strategy
from conftest import FakeExchange, as_ohlcv, make_candles
from settings import Settings


@pytest.fixture
def notifications(monkeypatch):
    sent = []
    monkeypatch.setattr(bot.notifier, 'send', lambda message: sent.append(message) or ['test'])
    return sent


@pytest.fixture
def trading_bot(monkeypatch):
    candles = make_candles([80000.0 + i for i in range(300)], start='2020-01-01')
    trading_bot = bot.Bot(Settings())
    trading_bot.exchange = FakeExchange(as_ohlcv(candles))
    return trading_bot


def force(monkeypatch, action):
    monkeypatch.setattr(strategy, 'signal', lambda *args: action)


def test_buy_records_the_amount_received_after_fees(db, trading_bot, notifications, monkeypatch):
    force(monkeypatch, 'buy')
    trading_bot.trade(db)
    position = storage.get_position(db, 'BTC/USDT', bot.testnet)
    order = trading_bot.exchange.orders[0]
    assert position['amount'] == pytest.approx(order['filled'] * 0.999)
    assert notifications[0].startswith('BUY')


def test_sell_includes_the_previous_leftover_and_keeps_the_new_one(db, trading_bot, notifications, monkeypatch):
    for _ in range(2):
        force(monkeypatch, 'buy')
        trading_bot.trade(db)
        force(monkeypatch, 'sell')
        trading_bot.trade(db)
    first_sell, second_sell = [order for order in trading_bot.exchange.orders if order['side'] == 'sell']
    assert second_sell['filled'] > first_sell['filled']
    assert 0 < storage.get_leftover(db, 'BTC/USDT', bot.testnet) < 0.00001
    assert storage.get_position(db, 'BTC/USDT', bot.testnet) is None


def test_does_not_buy_twice(db, trading_bot, notifications, monkeypatch):
    monkeypatch.setattr(strategy, 'wants_to_buy', lambda *args: True)
    monkeypatch.setattr(strategy, 'wants_to_sell', lambda *args: False)
    settings = replace(trading_bot.settings, trend_period=0)
    trading_bot.settings = settings
    trading_bot.trade(db)
    trading_bot.trade(db)
    assert len(trading_bot.exchange.orders) == 1


def test_daily_loss_limit_blocks_buys_and_notifies_once(db, trading_bot, notifications, monkeypatch):
    trading_bot.settings = replace(trading_bot.settings, daily_loss_limit_usdt=0.5)
    monkeypatch.setattr(bot, 'today_profit', lambda rows: -1.0)
    force(monkeypatch, 'buy')
    trading_bot.trade(db)
    trading_bot.trade(db)
    assert trading_bot.exchange.orders == []
    assert len(notifications) == 1
    assert 'Daily loss limit reached' in notifications[0]


def test_repeated_errors_are_notified_once(db, trading_bot, notifications, monkeypatch):
    def broken(*args):
        raise RuntimeError('exchange down')

    monkeypatch.setattr(strategy, 'signal', broken)
    trading_bot.trade(db)
    trading_bot.trade(db)
    force(monkeypatch, None)
    trading_bot.trade(db)
    monkeypatch.setattr(strategy, 'signal', broken)
    trading_bot.trade(db)
    assert notifications == ['Error: exchange down', 'Error: exchange down']


def test_start_and_stop(db, trading_bot, notifications, monkeypatch):
    force(monkeypatch, None)
    trading_bot.start()
    trading_bot.start()
    trading_bot.stop()
    trading_bot.thread.join(5)
    assert not trading_bot.running
    assert notifications[0].startswith('Bot started')
    assert notifications[-1] == 'Bot stopped'
