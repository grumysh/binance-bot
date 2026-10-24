from dataclasses import replace

import pytest

import backtest
from conftest import FakeExchange, dip_and_recovery, make_candles
from settings import Settings

SETTINGS = Settings(trend_period=0)


@pytest.fixture(autouse=True)
def fake_exchange(monkeypatch):
    monkeypatch.setattr(backtest, 'exchange', FakeExchange())


def test_buys_the_dip_and_sells_the_recovery():
    result = backtest.simulate(make_candles(dip_and_recovery()), SETTINGS, 0.001)
    assert len(result['trades']) == 1
    trade = result['trades'][0]
    assert trade['exit_price'] > trade['entry_price']
    assert trade['profit'] > 0
    assert trade['exit_reason'] == 'strategy'
    assert result['open_position'] is None


def test_buys_and_sells_at_the_open_of_the_next_candle():
    candles = make_candles(dip_and_recovery())
    trade = backtest.simulate(candles, SETTINGS, 0.001)['trades'][0]
    assert trade['entry_price'] == candles.loc[trade['entry_time'], 'open']
    assert trade['exit_price'] == candles.loc[trade['exit_time'], 'open']


def test_fees_lower_the_result():
    candles = make_candles(dip_and_recovery())
    without_fees = backtest.simulate(candles, SETTINGS, 0)['trades'][0]['profit']
    with_fees = backtest.simulate(candles, SETTINGS, 0.001)['trades'][0]['profit']
    assert with_fees < without_fees


def test_leftover_never_grows_beyond_one_step():
    result = backtest.simulate(make_candles(dip_and_recovery() * 6), SETTINGS, 0.001)
    assert len(result['trades']) > 1
    assert 0 <= result['leftover'] < 0.00001


def test_stop_loss_closes_the_trade_early():
    closes = dip_and_recovery()[:45] + [dip_and_recovery()[44] * (1 - 0.02 * (i + 1)) for i in range(10)]
    candles = make_candles(closes)
    without_stop = backtest.simulate(candles, SETTINGS, 0.001)
    with_stop = backtest.simulate(candles, replace(SETTINGS, stop_loss_percent=5), 0.001)
    assert without_stop['trades'] == []
    first = with_stop['trades'][0]
    assert first['exit_reason'] == 'stop loss'
    assert first['exit_price'] < first['entry_price'] * 0.95


def test_daily_loss_limit_stops_buying_for_the_day():
    closes = dip_and_recovery()[:45] + [dip_and_recovery()[44] * (1 - 0.02 * (i + 1)) for i in range(10)]
    closes += [closes[-1] * (1 - 0.01 * (i + 1)) for i in range(10)]
    candles = make_candles(closes, interval='5m', start='2026-01-01 12:00')
    stopped = replace(SETTINGS, interval='5m', stop_loss_percent=5)
    assert backtest.simulate(candles, stopped, 0.001)['open_position'] is not None
    limited = replace(stopped, daily_loss_limit_usdt=0.1)
    assert backtest.simulate(candles, limited, 0.001)['open_position'] is None


def test_metrics():
    result = backtest.simulate(make_candles(dip_and_recovery() * 3), SETTINGS, 0.001)
    m = backtest.metrics(result, SETTINGS)
    assert m['trades'] == len(result['trades'])
    assert m['win_rate'] == 100
    assert m['max_drawdown'] == 0
    assert m['total'] == pytest.approx(sum(trade['profit'] for trade in result['trades']))
    assert m['total_percent'] == pytest.approx(m['total'] / SETTINGS.order_size_usdt * 100)
