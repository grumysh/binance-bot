import asyncio
import time
from datetime import datetime

import pandas as pd
import pytest
from nicegui import ui
from nicegui.testing import User

import backtest
import bot
import compare
import components
import market
import notifier
import storage
import strategy
from conftest import FakeExchange, as_ohlcv, dip_and_recovery, make_candles
from settings import Settings


def candles():
    return make_candles(dip_and_recovery() * 4)


def fake_snapshot(exchange, settings):
    frame = strategy.add_indicators(candles(), settings)
    current, previous = frame.iloc[-1], frame.iloc[-2]
    return {
        'time': datetime.now(),
        'coin': settings.symbol.split('/')[0],
        'price': 81234.5,
        'last_close': current['close'],
        'rsi': current['rsi'],
        'trend': current['trend'],
        'indicators': strategy.describe(current, settings),
        'signal': None,
        'coin_balance': 1.0,
        'usdt_balance': 10000.0,
        'position': None,
        'chart': frame.tail(150),
        'trades': [],
        'today_profit': 0.0,
        'daily_limit_reached': False,
    }


def fake_backtest(settings, days, fee_rate):
    result = backtest.simulate(candles(), settings, fee_rate)
    return result, backtest.metrics(result, settings)


def fake_compare(db, symbols, days, fee_rate, base=None):
    rows = []
    for index, interval in enumerate(['1h', '4h']):
        settings = Settings(symbol=symbols[0], interval=interval, trend_period=0)
        rows.append({
            'symbol': symbols[0], 'interval': interval, 'strategy': strategy.name(settings), 'trend': 'off',
            'trades': 3 - index, 'win %': 66.7, 'profit factor': 1.5, 'max drawdown': 0.4,
            'avg duration': pd.Timedelta(hours=5), 'total USDT': 0.5 - index, 'total %': 5.0 - index * 10,
            'buy and hold %': 1.0, 'settings': settings.__dict__.copy(),
        })
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def offline_app(db, monkeypatch):
    exchange = FakeExchange(as_ohlcv(candles()))
    monkeypatch.setattr(bot, 'setup_logging', lambda: None)
    monkeypatch.setattr(market, 'create_exchange', lambda: exchange)
    monkeypatch.setattr(market, 'snapshot', fake_snapshot)
    monkeypatch.setattr(notifier, 'send', lambda message: [])
    monkeypatch.setattr(backtest, 'exchange', FakeExchange())
    monkeypatch.setattr(backtest, 'run', fake_backtest)
    monkeypatch.setattr(compare, 'compare', fake_compare)


async def wait_until(check, seconds=10):
    start = time.time()
    while time.time() - start < seconds:
        if check():
            return True
        await asyncio.sleep(0.2)
    return False


def labels(user):
    return [element.text for element in user.find(kind=ui.label).elements]


def element(user, label):
    return next(iter(user.find(content=label).elements))


async def test_bot_page_shows_market_and_chart(user: User):
    await user.open('/')
    await user.should_see('TESTNET')
    await user.should_see('81,234.50 USDT')
    await user.should_see('No open BTC/USDT position')
    await user.should_see('0 trades')
    chart = next(iter(user.find(kind=ui.echart).elements))
    assert [series['name'] for series in chart.options['series']][:2] == ['Price', 'Trend']


async def test_settings_are_validated_and_saved(user: User):
    await user.open('/')
    element(user, 'Buy when RSI is below').value = 80
    user.find(kind=ui.button, content='Save').click()
    await user.should_see('buy level below the sell level')
    assert storage.load_settings(storage.connect()) is None

    element(user, 'Buy when RSI is below').value = 30
    element(user, 'Symbol').value = 'ETH/USDT'
    user.find(kind=ui.button, content='Save').click()
    await user.should_see('Settings saved')
    assert storage.load_settings(storage.connect())['symbol'] == 'ETH/USDT'


async def test_strategy_fields_follow_the_selected_strategy(user: User):
    await user.open('/')
    await user.should_see('Buy when RSI is below')
    await user.should_not_see('Fast moving average (candles)')
    element(user, 'Strategy').value = 'ma_cross'
    await user.should_not_see('Buy when RSI is below')
    await user.should_see('Fast moving average (candles)')


async def test_start_and_stop(user: User):
    await user.open('/')
    user.find(kind=ui.button, content='Start').click()
    assert await wait_until(lambda: 'Running' in labels(user) or 'Stopping...' in labels(user))
    assert not element(user, 'Symbol').enabled
    user.find(kind=ui.button, content='Stop').click()
    assert await wait_until(lambda: 'Stopped' in labels(user))
    assert element(user, 'Symbol').enabled


@pytest.fixture
def real_account(monkeypatch):
    monkeypatch.setattr(bot, 'testnet', False)
    monkeypatch.setattr(components, 'testnet', False)


async def test_real_account_asks_to_type_real(real_account, user: User):
    await user.open('/')
    await user.should_see('REAL ACCOUNT: the bot trades with real money.')
    user.find(kind=ui.button, content='Start').click()
    await user.should_see('Trade with real money?')
    confirm = element(user, 'Start with real money')
    field = next(e for e in user.find(kind=ui.input).elements if e.props.get('placeholder') == 'REAL')
    assert not confirm.enabled
    field.value = 'real'
    assert not confirm.enabled
    field.value = 'REAL'
    assert confirm.enabled
    user.find(kind=ui.button, content='Cancel').click()
    await user.should_see('Stopped')


async def test_backtest_page_runs_and_compares(user: User):
    await user.open('/backtest')
    element(user, 'Trend filter (candles, 0 = off)').value = 0
    user.find(kind=ui.button, content='Run backtest').click()
    assert await wait_until(lambda: any('last 180 days' in text for text in labels(user)))
    tables = list(user.find(kind=ui.table).elements)
    assert tables[0].rows

    user.find(kind=ui.button, content='Compare').click()
    assert await wait_until(lambda: any(t.rows and 'strategy' in t.rows[0] for t in user.find(kind=ui.table).elements))
    table = next(t for t in user.find(kind=ui.table).elements if t.rows and 'strategy' in t.rows[0])
    interaction = user.find(kind=ui.table)
    interaction.elements = {table}
    interaction.trigger('rowClick', [None, table.rows[1]])
    assert element(user, 'Candle interval').value == '4h'
