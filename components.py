from dataclasses import asdict

from nicegui import ui

import storage
from market import testnet
from settings import INTERVALS, MIN_ORDER_USDT, SYMBOLS, Settings


def header(current):
    with ui.row().classes('w-full items-center justify-between'):
        with ui.row().classes('items-center gap-4'):
            ui.label('Binance Bot').classes('text-3xl font-bold')
            with ui.button_group().props('flat'):
                for title, path in [('Bot', '/'), ('Backtest', '/backtest')]:
                    button = ui.button(title, on_click=lambda path=path: ui.navigate.to(path))
                    button.props('unelevated' if title == current else 'flat')
        if testnet:
            ui.badge('TESTNET', color='green').classes('text-sm')
        else:
            ui.badge('REAL ACCOUNT', color='red').classes('text-sm')


def stat(title):
    with ui.column().classes('gap-0'):
        ui.label(title).classes('text-xs uppercase text-gray-500')
        return ui.label('-').classes('text-xl font-semibold')


def settings_form():
    with ui.grid(columns=2).classes('w-full gap-4'):
        inputs = {
            'symbol': ui.select(SYMBOLS, label='Symbol'),
            'interval': ui.select(INTERVALS, label='Candle interval'),
            'rsi_buy_below': ui.number('Buy when RSI is below', min=1, max=99),
            'rsi_sell_above': ui.number('Sell when RSI is above', min=1, max=99),
            'rsi_period': ui.number('RSI period', min=2, precision=0),
            'trend_period': ui.number('Trend filter (candles, 0 = off)', min=0, precision=0),
            'stop_loss_percent': ui.number('Stop loss (% below the buy price, 0 = off)', min=0, max=99, step=0.5),
            'order_size_usdt': ui.number(f'Order size (USDT, minimum {MIN_ORDER_USDT})', min=MIN_ORDER_USDT),
        }
    return inputs


def show_settings(inputs, settings):
    for name, value in asdict(settings).items():
        inputs[name].value = value


def read_settings(inputs):
    values = {name: element.value for name, element in inputs.items()}
    if any(value is None for value in values.values()):
        ui.notify('Fill in all the settings', type='negative')
        return None
    values['rsi_period'] = int(values['rsi_period'])
    values['trend_period'] = int(values['trend_period'])
    try:
        return Settings.from_dict(values)
    except ValueError as error:
        ui.notify(str(error), type='negative')
        return None


def apply_settings(trading_bot, settings):
    db = storage.connect()
    previous = trading_bot.settings
    storage.save_settings(db, asdict(settings))
    trading_bot.settings = settings
    trading_bot.last_check = None
    ui.notify('Settings saved', type='positive')
    if settings.symbol != previous.symbol and storage.get_position(db, previous.symbol, testnet):
        ui.notify(
            f'There is an open {previous.symbol} position. It stays open until you switch back to {previous.symbol}.',
            type='warning',
            timeout=10000,
        )
