from nicegui import run, ui

import backtest
import compare
import storage
import strategy
from bot import load_settings
from chart import chart_options, equity_options, trade_markers
from components import apply_settings, header, read_settings, settings_form, show_settings, stat
from journal import local_time
from settings import SYMBOLS, Settings

BACKTEST_COLUMNS = [
    {'name': 'entry_time', 'label': 'Bought', 'field': 'entry_time', 'align': 'left', 'sortable': True},
    {'name': 'entry_price', 'label': 'Buy price', 'field': 'entry_price', 'align': 'right'},
    {'name': 'exit_time', 'label': 'Sold', 'field': 'exit_time', 'align': 'left'},
    {'name': 'exit_price', 'label': 'Sell price', 'field': 'exit_price', 'align': 'right'},
    {'name': 'exit_reason', 'label': 'Exit', 'field': 'exit_reason', 'align': 'left'},
    {'name': 'duration', 'label': 'Duration', 'field': 'duration', 'align': 'right'},
    {'name': 'profit', 'label': 'Result (USDT)', 'field': 'profit', 'align': 'right'},
]


def format_duration(duration):
    return str(duration.round('1min')).replace('0 days ', '')


def run_comparison(symbols, days, fee_rate, base):
    return compare.compare(storage.connect(), symbols, days, fee_rate, base)


def register(trading_bot):
    @ui.page('/backtest')
    def backtest_view():
        with ui.column().classes('w-full max-w-5xl mx-auto p-6 gap-6'):
            header('Backtest')

            with ui.card().classes('w-full'):
                ui.label('Strategy to test').classes('text-lg font-semibold')
                inputs = settings_form()
                with ui.grid(columns=2).classes('w-full gap-4'):
                    days = ui.number('Days of history', value=180, min=7, max=1000, precision=0)
                    fee = ui.number('Fee per trade (%)', value=0.1, min=0, max=1, step=0.025)
                with ui.row().classes('items-center'):
                    run_button = ui.button('Run backtest', icon='play_arrow')
                    use_button = ui.button('Use these settings in the bot', icon='check').props('flat')
                    spinner = ui.spinner(size='lg')
                    progress = ui.label().classes('text-gray-500')
                spinner.visible = False

            with ui.card().classes('w-full') as results_card:
                results_title = ui.label().classes('text-lg font-semibold')
                with ui.grid(columns=4).classes('w-full gap-4'):
                    total = stat('Total result')
                    buy_and_hold = stat('Buy and hold')
                    trades_count = stat('Closed trades')
                    win_rate = stat('Win rate')
                    profit_factor = stat('Profit factor')
                    drawdown = stat('Max drawdown')
                    fees = stat('Fees paid')
                    duration = stat('Average duration')
                open_position = ui.label().classes('text-gray-600')
                ui.label('Price, trades and RSI').classes('font-semibold mt-4')
                price_chart = ui.echart({}).classes('w-full h-[480px]')
                ui.label('Accumulated result of the closed trades').classes('font-semibold mt-4')
                equity_chart = ui.echart({}).classes('w-full h-[240px]')
                trades_table = ui.table(
                    columns=BACKTEST_COLUMNS,
                    rows=[],
                    row_key='id',
                    pagination={'rowsPerPage': 10, 'sortBy': 'entry_time', 'descending': True},
                ).classes('w-full')
                trades_table.add_slot('body-cell-profit', '''
                    <q-td :props="props" :class="props.row.profit_value > 0 ? 'text-green-600' : 'text-red-600'">
                        {{ props.value }}
                    </q-td>
                ''')
            results_card.visible = False

            with ui.card().classes('w-full'):
                ui.label('Compare configurations').classes('text-lg font-semibold')
                ui.label(
                    'Tests every interval (5m, 15m, 1h, 4h), strategy (RSI 20/80, 25/75, 30/70 and 35/65, moving '
                    'average cross, Bollinger bands and MACD) and trend filter (off, 100, 200) with the days, fee, '
                    'stop loss and order size above. Click a row to load it in the form. A configuration that wins in '
                    'one period can lose in another, so check it with a different number of days.'
                ).classes('text-gray-600')
                with ui.row().classes('w-full items-center'):
                    compare_symbols = ui.select(SYMBOLS, multiple=True, label='Symbols').classes('min-w-[300px]')
                    compare_button = ui.button('Compare', icon='compare_arrows')
                compare_table = ui.table(columns=[], rows=[], row_key='id', pagination=10).classes('w-full')
                compare_table.visible = False

        settings = load_settings()
        show_settings(inputs, settings)
        compare_symbols.value = [settings.symbol]
        buttons = [run_button, use_button, compare_button]

        def set_busy(message):
            spinner.visible = bool(message)
            progress.text = message or ''
            for button in buttons:
                button.enabled = not message

        async def run_backtest():
            settings = read_settings(inputs)
            if settings is None or not days.value or fee.value is None:
                return
            fee_rate = fee.value / 100
            set_busy(f'Downloading candles and simulating {settings.symbol} {settings.interval}...')
            try:
                result, m = await run.io_bound(backtest.run, settings, int(days.value), fee_rate)
            except Exception as error:
                ui.notify(f'Backtest failed: {error}', type='negative')
                return
            finally:
                set_busy(None)
            show_results(settings, int(days.value), fee_rate, result, m)

        def show_results(settings, days_count, fee_rate, result, m):
            results_card.visible = True
            results_title.text = (
                f'{settings.symbol} {settings.interval} · last {days_count} days · {strategy.name(settings)} · trend filter {settings.trend_period or "off"} · '
                f'stop loss {f"{settings.stop_loss_percent:g}%" if settings.stop_loss_percent else "off"} · fee {fee_rate * 100:g}%'
            )
            total.text = f'{m["total"]:+.2f} USDT ({m["total_percent"]:+.1f}%)'
            total.classes(replace=f'text-xl font-semibold {"text-green-600" if m["total"] > 0 else "text-red-600"}')
            buy_and_hold.text = f'{m["buy_and_hold_percent"]:+.1f}%'
            trades_count.text = str(m['trades'])
            win_rate.text = f'{m["win_rate"]:.1f}%'
            profit_factor.text = 'No losses' if m['profit_factor'] == float('inf') else f'{m["profit_factor"]:.2f}'
            drawdown.text = f'{m["max_drawdown"]:.2f} USDT'
            fees.text = f'{m["fees"]:.2f} USDT'
            duration.text = format_duration(m['average_duration']) if m['trades'] else '-'
            open_position.text = (
                f'Open position at the end: {m["open_profit"]:+.2f} USDT' if m['open_profit'] is not None
                else 'No open position at the end'
            )

            markers = trade_markers(result['trades'], result['open_position'])
            price_chart.options.clear()
            price_chart.options.update(chart_options(result['candles'], markers, settings))
            price_chart.update()
            equity_chart.options.clear()
            equity_chart.options.update(equity_options(result['trades']))
            equity_chart.update()

            trades_table.rows = [
                {
                    'id': index,
                    'entry_time': local_time(trade['entry_time']),
                    'entry_price': f'{trade["entry_price"]:,.2f}',
                    'exit_time': local_time(trade['exit_time']),
                    'exit_price': f'{trade["exit_price"]:,.2f}',
                    'exit_reason': trade['exit_reason'],
                    'duration': format_duration(trade['exit_time'] - trade['entry_time']),
                    'profit': f'{trade["profit"]:+.4f}',
                    'profit_value': trade['profit'],
                }
                for index, trade in enumerate(result['trades'])
            ]

        async def run_compare():
            base = read_settings(inputs)
            if base is None:
                return
            if not compare_symbols.value or not days.value or fee.value is None:
                ui.notify('Choose at least one symbol, the days and the fee', type='negative')
                return
            count = len(compare_symbols.value) * compare.CONFIGURATIONS
            set_busy(f'Comparing {count} configurations, this can take a few minutes...')
            try:
                results = await run.io_bound(
                    run_comparison, compare_symbols.value, int(days.value), fee.value / 100, base,
                )
            except Exception as error:
                ui.notify(f'Comparison failed: {error}', type='negative')
                return
            finally:
                set_busy(None)

            results = results.assign(id=range(len(results)), **{'avg duration': results['avg duration'].map(format_duration)})
            compare_table.columns = [
                {
                    'name': column,
                    'label': column.capitalize(),
                    'field': column,
                    'align': 'left' if column in ('symbol', 'interval', 'strategy', 'trend') else 'right',
                    'sortable': True,
                }
                for column in results.columns if column not in ('id', 'settings')
            ]
            compare_table.rows = results.to_dict('records')
            compare_table.visible = True

        def load_row(event):
            row = event.args[1]
            show_settings(inputs, Settings.from_dict(row['settings']))
            ui.notify(
                f'Loaded {row["symbol"]} {row["interval"]} {row["strategy"]} trend {row["trend"]}. '
                'Run the backtest to see it.'
            )

        def use_settings():
            new_settings = read_settings(inputs)
            if new_settings is None:
                return
            if trading_bot.running:
                ui.notify('Stop the bot before changing its settings', type='warning')
                return
            apply_settings(trading_bot, new_settings)

        run_button.on_click(run_backtest)
        compare_button.on_click(run_compare)
        use_button.on_click(use_settings)
        compare_table.on('rowClick', load_row)
