import pytest

from settings import Settings


def test_defaults_are_valid():
    settings = Settings()
    assert (settings.symbol, settings.interval, settings.strategy, settings.trend_period) == ('BTC/USDT', '1h', 'rsi', 200)


@pytest.mark.parametrize('values', [
    {'symbol': 'PEPE/USDT'},
    {'interval': '2h'},
    {'strategy': 'magic'},
    {'rsi_period': 1},
    {'rsi_buy_below': 70, 'rsi_sell_above': 30},
    {'rsi_sell_above': 100},
    {'ma_fast_period': 50, 'ma_slow_period': 20},
    {'bollinger_deviations': 0},
    {'trend_period': -1},
    {'stop_loss_percent': 100},
    {'daily_loss_limit_usdt': -1},
    {'order_size_usdt': 4},
])
def test_invalid_settings_are_rejected(values):
    with pytest.raises(ValueError):
        Settings(**values)


def test_from_dict_ignores_unknown_fields():
    settings = Settings.from_dict({'symbol': 'ETH/USDT', 'removed_field': True})
    assert settings.symbol == 'ETH/USDT'
