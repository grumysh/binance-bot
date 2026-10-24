from datetime import datetime, timedelta, timezone

import pytest

import journal


def trade(side, amount, price, fee, fee_currency, symbol='BTC/USDT', time='2026-10-20T10:00:00Z', cost=None):
    return {
        'id': 1, 'time': time, 'symbol': symbol, 'side': side, 'amount': amount, 'price': price,
        'cost': amount * price if cost is None else cost, 'fee': fee, 'fee_currency': fee_currency,
    }


def test_fee_in_usdt():
    assert journal.fee_in_usdt(trade('buy', 0.001, 80000, 0.000001, 'BTC')) == pytest.approx(0.08)
    assert journal.fee_in_usdt(trade('sell', 0.001, 80000, 0.08, 'USDT')) == 0.08


def test_result_uses_the_cost_of_the_amount_sold():
    rows = journal.journal([
        trade('buy', 0.00011988, 80000, 0.00000012, 'BTC', cost=9.6),
        trade('sell', 0.00011, 82000, 0.00902, 'USDT'),
    ])
    assert rows[0]['profit'] is None
    assert rows[1]['profit_percent'] == pytest.approx(2.29, abs=0.01)


def test_sells_are_paired_per_symbol():
    rows = journal.journal([
        trade('buy', 0.001, 80000, 0, 'BTC'),
        trade('buy', 0.01, 2000, 0, 'ETH', symbol='ETH/USDT'),
        trade('sell', 0.01, 2200, 0, 'USDT', symbol='ETH/USDT'),
        trade('sell', 0.001, 72000, 0, 'USDT'),
    ])
    assert rows[2]['profit'] == pytest.approx(2.0)
    assert rows[3]['profit'] == pytest.approx(-8.0)
    totals = journal.summary(rows)
    assert totals['closed'] == 2
    assert totals['win_rate'] == 50
    assert totals['profit'] == pytest.approx(-6.0)


def test_today_profit_ignores_previous_days():
    now = datetime.now(timezone.utc)
    rows = [
        {'time': (now - timedelta(days=2)).isoformat(), 'profit': -3.0},
        {'time': (now - timedelta(minutes=1)).isoformat(), 'profit': -0.5},
        {'time': (now - timedelta(minutes=1)).isoformat(), 'profit': None},
    ]
    assert journal.today_profit(rows) == -0.5
