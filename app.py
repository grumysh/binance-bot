from nicegui import run, ui

import backtest_page
import market
import notifier
import storage
from bot import Bot, load_settings, setup_logging, testnet
from chart import chart_options
from components import apply_settings, header, read_settings, settings_form, show_settings, stat
from journal import journal, local_time, summary
from settings import Settings

setup_logging()
trading_bot = Bot(load_settings())
dashboard_exchange = market.create_exchange()

SIGNAL_TEXT = {'buy': 'Buy', 'sell': 'Sell', 'stop_loss': 'Stop loss', None: 'Wait'}

TRADE_COLUMNS = [
    {'name': 'time', 'label': 'Time', 'field': 'time', 'align': 'left', 'sortable': True},
    {'name': 'symbol', 'label': 'Symbol', 'field': 'symbol', 'align': 'left', 'sortable': True},
    {'name': 'side', 'label': 'Side', 'field': 'side', 'align': 'left'},
    {'name': 'amount', 'label': 'Amount', 'field': 'amount', 'align': 'right'},
    {'name': 'price', 'label': 'Price', 'field': 'price', 'align': 'right'},
    {'name': 'cost', 'label': 'Value (USDT)', 'field': 'cost', 'align': 'right'},
    {'name': 'fee', 'label': 'Fee (USDT)', 'field': 'fee', 'align': 'right'},
    {'name': 'profit', 'label': 'Result (USDT)', 'field': 'profit', 'align': 'right'},
]


@ui.page('/')
def index():
    with ui.column().classes('w-full max-w-3xl mx-auto p-6 gap-6'):
        header('Bot')

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                status = ui.label().classes('text-lg font-semibold')
                with ui.row():
                    start_button = ui.button('Start', icon='play_arrow', color='green')
                    stop_button = ui.button('Stop', icon='stop', color='red')
            last_check = ui.label().classes('text-gray-500')

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Market and account').classes('text-lg font-semibold')
                updated = ui.label().classes('text-gray-500 text-sm')
            with ui.grid(columns=3).classes('w-full gap-4'):
                price = stat('Price')
                rsi = stat('Indicators (last closed candle)')
                trend = stat('Trend filter')
                usdt_balance = stat('USDT balance')
                coin_balance = stat('Coin balance')
                signal = stat('Signal now')
            position = ui.label().classes('text-gray-600')
            today = ui.label().classes('text-gray-600')

        with ui.card().classes('w-full'):
            ui.label('Chart').classes('text-lg font-semibold')
            price_chart = ui.echart({}).classes('w-full h-[480px]')

        with ui.card().classes('w-full'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Trades').classes('text-lg font-semibold')
                trades_search = ui.input(placeholder='Search').props('dense clearable')
            trades_summary = ui.label().classes('text-gray-600')
            trades_table = ui.table(
                columns=TRADE_COLUMNS,
                rows=[],
                row_key='id',
                pagination={'rowsPerPage': 10, 'sortBy': 'time', 'descending': True},
            ).classes('w-full')
            trades_table.add_slot('body-cell-side', '''
                <q-td :props="props">
                    <q-badge :color="props.value === 'BUY' ? 'green' : 'red'">{{ props.value }}</q-badge>
                </q-td>
            ''')
            trades_table.add_slot('body-cell-profit', '''
                <q-td :props="props" :class="props.row.profit_value > 0 ? 'text-green-600' : props.row.profit_value < 0 ? 'text-red-600' : ''">
                    {{ props.value }}
                </q-td>
            ''')
            trades_search.bind_value_to(trades_table, 'filter')

        with ui.card().classes('w-full'):
            ui.label('Notifications').classes('text-lg font-semibold')
            with ui.row().classes('w-full items-center justify-between'):
                configured = notifier.channels()
                if configured:
                    ui.label(f'Sending to {" and ".join(configured)} on start, stop, buys, sells and errors.')
                else:
                    ui.label(
                        'No channels configured. Add DISCORD_WEBHOOK_URL, or TELEGRAM_BOT_TOKEN and '
                        'TELEGRAM_CHAT_ID, to .env and restart the app.'
                    ).classes('text-gray-600')
                test_button = ui.button('Send test', icon='notifications')
                test_button.enabled = bool(configured)

        with ui.card().classes('w-full'):
            ui.label('Settings').classes('text-lg font-semibold')
            settings_hint = ui.label('Stop the bot to change the settings.').classes('text-orange-600')
            inputs = settings_form()
            with ui.row():
                save_button = ui.button('Save', icon='save')
                defaults_button = ui.button('Restore defaults', icon='restart_alt').props('flat')

    async def save():
        settings = read_settings(inputs)
        if settings is None:
            return
        apply_settings(trading_bot, settings)
        await refresh_market()

    async def send_test():
        sent = await run.io_bound(notifier.send, 'Test notification from the Binance bot')
        if sent:
            ui.notify(f'Sent to {" and ".join(sent)}', type='positive')
        else:
            ui.notify('Could not send it, check the log', type='negative')

    test_button.on_click(send_test)
    save_button.on_click(save)
    defaults_button.on_click(lambda: show_settings(inputs, Settings()))
    show_settings(inputs, trading_bot.settings)

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
                f'{check["indicators"]} · trend {check["trend"]:.2f}'
            )
        else:
            last_check.text = 'No checks yet'

    loading = False
    chart_key = None
    trades_count = None

    def refresh_trades():
        nonlocal trades_count
        rows = journal(storage.get_all_trades(storage.connect(), testnet))
        if len(rows) == trades_count:
            return
        trades_count = len(rows)
        totals = summary(rows)
        trades_summary.text = (
            f'{len(rows)} trades · {totals["closed"]} closed · {totals["win_rate"]:.0f}% won · '
            f'result {totals["profit"]:+.2f} USDT · fees {totals["fees"]:.2f} USDT'
        )
        trades_table.rows = [
            {
                'id': row['id'],
                'time': local_time(row['time']),
                'symbol': row['symbol'],
                'side': row['side'].upper(),
                'amount': f'{row["amount"]:.8f}',
                'price': f'{row["price"]:,.2f}',
                'cost': f'{row["cost"]:,.2f}',
                'fee': f'{row["fee_usdt"]:.4f}',
                'profit': '' if row['profit'] is None else f'{row["profit"]:+.4f} ({row["profit_percent"]:+.2f}%)',
                'profit_value': row['profit'] or 0,
            }
            for row in rows
        ]

    async def refresh_market():
        nonlocal loading, chart_key
        if loading:
            return
        loading = True
        settings = trading_bot.settings
        try:
            data = await run.io_bound(market.snapshot, dashboard_exchange, settings)
        except Exception as error:
            updated.text = f'Could not load: {error}'
            return
        finally:
            loading = False
        if data is None:
            return
        refresh_trades()

        coin = data['coin']
        price.text = f'{data["price"]:,.2f} USDT'
        rsi.text = data['indicators']
        rsi.classes(replace='text-xl font-semibold')
        if settings.strategy == 'rsi' and data['rsi'] < settings.rsi_buy_below:
            rsi.classes('text-green-600')
        elif settings.strategy == 'rsi' and data['rsi'] > settings.rsi_sell_above:
            rsi.classes('text-red-600')

        if settings.trend_period:
            above = data['last_close'] > data['trend']
            trend.text = f'{"Above" if above else "Below"} {data["trend"]:,.2f}'
            trend.classes(replace=f'text-xl font-semibold {"text-green-600" if above else "text-orange-600"}')
        else:
            trend.text = 'Off'
            trend.classes(replace='text-xl font-semibold')

        usdt_balance.text = f'{data["usdt_balance"]:,.2f}'
        coin_balance.text = f'{data["coin_balance"]:,.8f} {coin}'
        signal.text = SIGNAL_TEXT[data['signal']]

        open_position = data['position']
        if open_position:
            profit = open_position['profit']
            position.text = (
                f'Open position: {open_position["amount"]:.8f} {coin} bought at {open_position["entry_price"]:,.2f} '
                f'for {open_position["cost"]:.2f} USDT · now worth {open_position["value"]:.2f} USDT · '
                f'{profit:+.2f} USDT ({open_position["profit_percent"]:+.2f}%)'
            )
            position.classes(replace='text-green-600' if profit >= 0 else 'text-red-600')
        else:
            position.text = f'No open {settings.symbol} position'
            position.classes(replace='text-gray-600')
        today.text = f'Today: {data["today_profit"]:+.2f} USDT from closed trades'
        if settings.daily_loss_limit_usdt:
            today.text += f' · daily loss limit {settings.daily_loss_limit_usdt:g} USDT'
        if data['daily_limit_reached']:
            today.text += ' · limit reached, no new buys until tomorrow'
            today.classes(replace='text-red-600')
        else:
            today.classes(replace='text-gray-600')
        updated.text = f'Updated {data["time"]:%H:%M:%S}'

        key = (settings, data['chart'].index[-1], len(data['trades']))
        if key != chart_key:
            chart_key = key
            price_chart.options.clear()
            price_chart.options.update(chart_options(data['chart'], data['trades'], settings))
            price_chart.update()

    start_button.on_click(lambda: (trading_bot.start(), refresh()))
    stop_button.on_click(lambda: (trading_bot.stop(), refresh()))
    refresh()
    ui.timer(1.0, refresh)
    ui.timer(15.0, refresh_market)
    ui.timer(0, refresh_market, once=True)


backtest_page.register(trading_bot)

if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='Binance Bot', port=8080, reload=False, show=False)
