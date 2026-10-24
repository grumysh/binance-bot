from dataclasses import replace

import pytest

import strategy
from conftest import dip_and_recovery, make_candles
from settings import Settings

RSI = Settings(trend_period=0)


def row(**values):
    return {'close': 100.0, 'trend': 90.0, 'rsi': 50.0, **values}


@pytest.mark.parametrize('rsi, expected', [(25, 'buy'), (30, None), (50, None)])
def test_rsi_buys_below_the_buy_level(rsi, expected):
    assert strategy.signal(row(rsi=rsi), row(), None, RSI) == expected


@pytest.mark.parametrize('rsi, expected', [(75, 'sell'), (70, None), (20, None)])
def test_rsi_sells_above_the_sell_level(rsi, expected):
    assert strategy.signal(row(rsi=rsi), row(), 100.0, RSI) == expected


def test_trend_filter_blocks_buys_below_the_trend():
    settings = replace(RSI, trend_period=200)
    assert strategy.signal(row(rsi=20, close=100, trend=110), row(), None, settings) is None
    assert strategy.signal(row(rsi=20, close=100, trend=90), row(), None, settings) == 'buy'


def test_trend_filter_never_blocks_sells():
    settings = replace(RSI, trend_period=200)
    assert strategy.signal(row(rsi=80, close=100, trend=110), row(), 100.0, settings) == 'sell'


def test_stop_loss_sells_before_the_strategy_does():
    settings = replace(RSI, stop_loss_percent=5)
    assert strategy.signal(row(close=96), row(), 100.0, settings) is None
    assert strategy.signal(row(close=95), row(), 100.0, settings) == 'stop_loss'
    assert strategy.signal(row(close=50), row(), 100.0, RSI) is None


def test_moving_average_cross():
    settings = replace(RSI, strategy='ma_cross')
    assert strategy.signal(row(fast=11, slow=10), row(fast=9, slow=10), None, settings) == 'buy'
    assert strategy.signal(row(fast=12, slow=10), row(fast=11, slow=10), None, settings) is None
    assert strategy.signal(row(fast=9, slow=10), row(fast=11, slow=10), 100.0, settings) == 'sell'


def test_bollinger_bands():
    settings = replace(RSI, strategy='bollinger')
    bands = {'lower': 95.0, 'middle': 100.0, 'upper': 105.0}
    assert strategy.signal(row(close=94, **bands), row(), None, settings) == 'buy'
    assert strategy.signal(row(close=96, **bands), row(), None, settings) is None
    assert strategy.signal(row(close=101, **bands), row(), 94.0, settings) == 'sell'


def test_macd_cross():
    settings = replace(RSI, strategy='macd')
    assert strategy.signal(row(macd=1, macd_signal=0), row(macd=-1, macd_signal=0), None, settings) == 'buy'
    assert strategy.signal(row(macd=-1, macd_signal=0), row(macd=1, macd_signal=0), 100.0, settings) == 'sell'


def test_daily_limit():
    settings = replace(RSI, daily_loss_limit_usdt=1)
    assert not strategy.daily_limit_reached(-0.5, settings)
    assert strategy.daily_limit_reached(-1.0, settings)
    assert not strategy.daily_limit_reached(-100, RSI)


@pytest.mark.parametrize('name', ['rsi', 'ma_cross', 'bollinger', 'macd'])
def test_every_strategy_adds_what_it_needs(name):
    settings = replace(RSI, strategy=name)
    candles = strategy.add_indicators(make_candles(dip_and_recovery() * 2), settings)
    columns, _ = strategy.lower_panel(settings)
    lines = [*strategy.price_lines(settings), *columns]
    needed = ['rsi', 'trend', *[column for column, _ in lines]]
    assert set(needed) <= set(candles.columns)
    assert strategy.describe(candles.iloc[-1], settings)
    assert strategy.name(settings)
