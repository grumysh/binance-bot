from nicegui import ui

from bot import Bot, setup_logging, testnet
from settings import Settings

setup_logging()
trading_bot = Bot(Settings())


@ui.page('/')
def index():
    settings = trading_bot.settings

    with ui.column().classes('w-full max-w-3xl mx-auto p-6 gap-6'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Binance Bot').classes('text-3xl font-bold')
            if testnet:
                ui.badge('TESTNET', color='green').classes('text-sm')
            else:
                ui.badge('REAL ACCOUNT', color='red').classes('text-sm')

        with ui.card().classes('w-full'):
            ui.label('Settings').classes('text-lg font-semibold')
            ui.label(
                f'{settings.symbol} · {settings.interval} candles · RSI {settings.rsi_period} '
                f'buy < {settings.rsi_buy_below}, sell > {settings.rsi_sell_above} · '
                f'trend filter {settings.trend_period or "off"} · {settings.order_size_usdt} USDT per trade'
            )

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                status = ui.label().classes('text-lg font-semibold')
                with ui.row():
                    start_button = ui.button('Start', icon='play_arrow', color='green', on_click=trading_bot.start)
                    stop_button = ui.button('Stop', icon='stop', color='red', on_click=trading_bot.stop)
            last_check = ui.label().classes('text-gray-500')

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

        check = trading_bot.last_check
        if check:
            last_check.text = (
                f'Last check {check["time"]:%H:%M:%S} · close {check["close"]} · '
                f'RSI {check["rsi"]:.2f} · trend {check["trend"]:.2f}'
            )
        else:
            last_check.text = 'No checks yet'

    refresh()
    ui.timer(1.0, refresh)


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='Binance Bot', port=8080, reload=False, show=False)
