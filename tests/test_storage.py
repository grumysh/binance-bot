import storage


def order(side, amount, price, order_id='1', time='2026-10-20T10:00:00Z'):
    return {
        'id': order_id, 'symbol': 'BTC/USDT', 'datetime': time, 'filled': amount, 'average': price,
        'cost': amount * price, 'fees': [],
    }


def test_buy_opens_a_position_and_sell_closes_it(db):
    storage.record_buy(db, order('buy', 0.001, 80000), 0.001, True)
    position = storage.get_position(db, 'BTC/USDT', True)
    assert position['amount'] == 0.001
    assert storage.get_position(db, 'BTC/USDT', False) is None

    storage.record_sell(db, order('sell', 0.001, 82000, order_id='2'), True, 0.000004)
    assert storage.get_position(db, 'BTC/USDT', True) is None
    assert storage.get_leftover(db, 'BTC/USDT', True) == 0.000004
    assert [trade['side'] for trade in storage.get_all_trades(db, True)] == ['buy', 'sell']
    assert storage.get_all_trades(db, False) == []


def test_leftover_is_replaced_on_each_sell(db):
    storage.record_sell(db, order('sell', 0.001, 82000), True, 0.000004)
    storage.record_sell(db, order('sell', 0.001, 82000, order_id='2'), True, 0.000001)
    assert storage.get_leftover(db, 'BTC/USDT', True) == 0.000001


def test_settings_round_trip(db):
    assert storage.load_settings(db) is None
    storage.save_settings(db, {'symbol': 'ETH/USDT'})
    storage.save_settings(db, {'symbol': 'SOL/USDT'})
    assert storage.load_settings(db) == {'symbol': 'SOL/USDT'}


def test_candles_are_not_duplicated(db):
    candles = [[1000, 1, 2, 0.5, 1.5, 10], [2000, 1.5, 2, 1, 1.8, 12]]
    storage.save_candles(db, 'BTC/USDT', '1h', candles)
    storage.save_candles(db, 'BTC/USDT', '1h', candles)
    assert tuple(storage.candle_range(db, 'BTC/USDT', '1h')) == (1000, 2000)
    assert len(storage.load_candles(db, 'BTC/USDT', '1h', 0)) == 2
    assert len(storage.load_candles(db, 'BTC/USDT', '1h', 1500)) == 1
