from datetime import datetime

import pandas as pd

GREEN = '#16a34a'
RED = '#dc2626'
ORANGE = '#f59e0b'
BLUE = '#2563eb'


def to_list(series, decimals):
    return [None if pd.isna(value) else round(float(value), decimals) for value in series]


def trade_points(trades, times, side, labels):
    points = []
    for trade in trades:
        if trade['side'] != side:
            continue
        position = times.searchsorted(pd.Timestamp(trade['time']), side='right') - 1
        if position >= 0:
            points.append([labels[position], trade['price']])
    return points


def chart_options(candles, trades, settings):
    local_times = candles.index.tz_convert(datetime.now().astimezone().tzinfo)
    labels = [time.strftime('%m-%d %H:%M') for time in local_times]
    prices = candles[['open', 'close', 'low', 'high']].round(8).values.tolist()

    return {
        'animation': False,
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'cross'}},
        'axisPointer': {'link': [{'xAxisIndex': 'all'}]},
        'legend': {'data': ['Price', 'Trend', 'Buy', 'Sell', 'RSI'], 'top': 0},
        'grid': [
            {'left': 70, 'right': 20, 'top': 40, 'height': '52%'},
            {'left': 70, 'right': 20, 'top': '70%', 'height': '15%'},
        ],
        'xAxis': [
            {'type': 'category', 'data': labels, 'axisLabel': {'show': False}},
            {'type': 'category', 'data': labels, 'gridIndex': 1},
        ],
        'yAxis': [
            {'scale': True},
            {'gridIndex': 1, 'min': 0, 'max': 100, 'interval': 50},
        ],
        'dataZoom': [
            {'type': 'inside', 'xAxisIndex': [0, 1], 'start': 40, 'end': 100},
            {'type': 'slider', 'xAxisIndex': [0, 1], 'bottom': 5, 'height': 20},
        ],
        'series': [
            {
                'name': 'Price',
                'type': 'candlestick',
                'data': prices,
                'itemStyle': {'color': GREEN, 'color0': RED, 'borderColor': GREEN, 'borderColor0': RED},
            },
            {
                'name': 'Trend',
                'type': 'line',
                'data': to_list(candles['trend'], 2),
                'showSymbol': False,
                'lineStyle': {'width': 1.5, 'color': ORANGE},
                'itemStyle': {'color': ORANGE},
            },
            {
                'name': 'Buy',
                'type': 'scatter',
                'data': trade_points(trades, candles.index, 'buy', labels),
                'symbol': 'triangle',
                'symbolSize': 14,
                'itemStyle': {'color': GREEN},
            },
            {
                'name': 'Sell',
                'type': 'scatter',
                'data': trade_points(trades, candles.index, 'sell', labels),
                'symbol': 'triangle',
                'symbolRotate': 180,
                'symbolSize': 14,
                'itemStyle': {'color': RED},
            },
            {
                'name': 'RSI',
                'type': 'line',
                'xAxisIndex': 1,
                'yAxisIndex': 1,
                'data': to_list(candles['rsi'], 2),
                'showSymbol': False,
                'lineStyle': {'width': 1.5, 'color': BLUE},
                'itemStyle': {'color': BLUE},
                'markLine': {
                    'silent': True,
                    'symbol': 'none',
                    'lineStyle': {'type': 'dashed', 'color': '#9ca3af'},
                    'data': [{'yAxis': settings.rsi_buy_below}, {'yAxis': settings.rsi_sell_above}],
                },
            },
        ],
    }


def trade_markers(trades, open_position):
    markers = []
    for trade in trades:
        markers.append({'side': 'buy', 'time': trade['entry_time'], 'price': trade['entry_price']})
        markers.append({'side': 'sell', 'time': trade['exit_time'], 'price': trade['exit_price']})
    if open_position:
        markers.append({'side': 'buy', 'time': open_position['entry_time'], 'price': open_position['entry_price']})
    return markers


def equity_options(trades):
    local_zone = datetime.now().astimezone().tzinfo
    labels = [trade['exit_time'].tz_convert(local_zone).strftime('%m-%d %H:%M') for trade in trades]
    total = 0.0
    equity = []
    for trade in trades:
        total += trade['profit']
        equity.append(round(total, 4))

    return {
        'animation': False,
        'tooltip': {'trigger': 'axis'},
        'grid': {'left': 70, 'right': 20, 'top': 20, 'bottom': 40},
        'xAxis': {'type': 'category', 'data': labels},
        'yAxis': {'type': 'value', 'name': 'USDT'},
        'series': [{
            'name': 'Accumulated result',
            'type': 'line',
            'data': equity,
            'step': 'end',
            'showSymbol': False,
            'lineStyle': {'color': BLUE},
            'itemStyle': {'color': BLUE},
            'areaStyle': {'opacity': 0.1, 'color': BLUE},
        }],
    }
