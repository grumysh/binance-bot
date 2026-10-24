from dataclasses import asdict

from nicegui import ui

import storage
from bot import Bot, load_settings, setup_logging, testnet
from settings import INTERVALS, MIN_ORDER_USDT, SYMBOLS, Settings

setup_logging()
trading_bot = Bot(load_settings())


@ui.page('/')
def index():
    with ui.column().classes('w-full max-w-3xl mx-auto p-6 gap-6'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Binance Bot').classes('text-3xl font-bold')
            if testnet:
                ui.badge('TESTNET', color='green').classes('text-sm')
            else:
                ui.badge('REAL ACCOUNT', color='red').classes('text-sm')

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                status = ui.label().classes('text-lg font-semibold')
                with ui.row():
                    start_button = ui.button('Start', icon='play_arrow', color='green', on_click=trading_bot.start)
                    stop_button = ui.button('Stop', icon='stop', color='red', on_click=trading_bot.stop)
            last_check = ui.label().classes('text-gray-500')

        with ui.card().classes('w-full'):
            ui.label('Settings').classes('text-lg font-semibold')
            settings_hint = ui.label('Stop the bot to change the settings.').classes('text-orange-600')
            with ui.grid(columns=2).classes('w-full gap-4'):
                symbol = ui.select(SYMBOLS, label='Symbol')
                interval = ui.select(INTERVALS, label='Candle interval')
                rsi_buy_below = ui.number('Buy when RSI is below', min=1, max=99)
                rsi_sell_above = ui.number('Sell when RSI is above', min=1, max=99)
                rsi_period = ui.number('RSI period', min=2, precision=0)
                trend_period = ui.number('Trend filter (candles, 0 = off)', min=0, precision=0)
                order_size_usdt = ui.number(f'Order size (USDT, minimum {MIN_ORDER_USDT})', min=MIN_ORDER_USDT)
            inputs = {
                'symbol': symbol,
                'interval': interval,
                'rsi_period': rsi_period,
                'rsi_buy_below': rsi_buy_below,
                'rsi_sell_above': rsi_sell_above,
                'trend_period': trend_period,
                'order_size_usdt': order_size_usdt,
            }
            with ui.row():
                save_button = ui.button('Save', icon='save')
                defaults_button = ui.button('Restore defaults', icon='restart_alt').props('flat')

    def show_settings(settings):
        for name, value in asdict(settings).items():
            inputs[name].value = value

    def save():
        values = {name: element.value for name, element in inputs.items()}
        if any(value is None for value in values.values()):
            ui.notify('Fill in all the settings', type='negative')
            return
        values['rsi_period'] = int(values['rsi_period'])
        values['trend_period'] = int(values['trend_period'])
        try:
            settings = Settings.from_dict(values)
        except ValueError as error:
            ui.notify(str(error), type='negative')
            return

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

    save_button.on_click(save)
    defaults_button.on_click(lambda: show_settings(Settings()))
    show_settings(trading_bot.settings)

    def refresh():
        stopping = trading_bot.running and trading_bot.stop_requested.is_set()
        if stopping:
            status.text = 'Stopping...'
        elif trading_bot.running:
            status.text = 'Running'
        else:
            status.text = 'Stopped'
        start_button.enabled = not trading_bot.running
        stop_button.enabled = trading_bot.running and not stopping

        editable = not trading_bot.running
        for element in [*inputs.values(), save_button, defaults_button]:
            element.enabled = editable
        settings_hint.visible = not editable

        check = trading_bot.last_check
        if check:
            last_check.text = (
                f'Last check {check["time"]:%H:%M:%S} · {trading_bot.settings.symbol} close {check["close"]} · '
                f'RSI {check["rsi"]:.2f} · trend {check["trend"]:.2f}'
            )
        else:
            last_check.text = 'No checks yet'

    refresh()
    ui.timer(1.0, refresh)


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='Binance Bot', port=8080, reload=False, show=False)
