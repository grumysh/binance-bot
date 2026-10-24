from datetime import datetime

import pandas as pd

import strategy

GREEN = '#16a34a'
RED = '#dc2626'
ORANGE = '#f59e0b'
BLUE = '#2563eb'
LINE_COLORS = ['#2563eb', '#7c3aed', '#6b7280', '#dc2626']


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


def line(name, data, color, axis=0, dashed=False):
    return {
        'name': name,
        'type': 'line',
        'xAxisIndex': axis,
        'yAxisIndex': axis,
        'data': data,
        'showSymbol': False,
        'lineStyle': {'width': 1.5, 'color': color, 'type': 'dashed' if dashed else 'solid'},
        'itemStyle': {'color': color},
    }


def chart_options(candles, trades, settings):
    local_times = candles.index.tz_convert(datetime.now().astimezone().tzinfo)
    labels = [time.strftime('%m-%d %H:%M') for time in local_times]
    prices = candles[['open', 'close', 'low', 'high']].round(8).values.tolist()
    price_lines = [
        line(name, to_list(candles[column], 2), color, dashed=True)
        for (column, name), color in zip(strategy.price_lines(settings), LINE_COLORS)
    ]
    lower_columns, levels = strategy.lower_panel(settings)
    lower_lines = [
        line(name, to_list(candles[column], 4), color, axis=1)
        for (column, name), color in zip(lower_columns, LINE_COLORS[::3])
    ]
    if levels:
        lower_lines[0]['markLine'] = {
            'silent': True,
            'symbol': 'none',
            'lineStyle': {'type': 'dashed', 'color': '#9ca3af'},
            'data': [{'yAxis': level} for level in levels],
        }
    lower_axis = {'gridIndex': 1, 'min': 0, 'max': 100, 'interval': 50} if levels else {'gridIndex': 1, 'scale': True, 'splitNumber': 2}

    series = [
        {
            'name': 'Price',
            'type': 'candlestick',
            'data': prices,
            'itemStyle': {'color': GREEN, 'color0': RED, 'borderColor': GREEN, 'borderColor0': RED},
        },
        line('Trend', to_list(candles['trend'], 2), ORANGE),
        *price_lines,
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
        *lower_lines,
    ]

    return {
        'animation': False,
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'cross'}},
        'axisPointer': {'link': [{'xAxisIndex': 'all'}]},
        'legend': {'data': [item['name'] for item in series], 'top': 0},
        'grid': [
            {'left': 70, 'right': 20, 'top': 40, 'height': '52%'},
            {'left': 70, 'right': 20, 'top': '70%', 'height': '15%'},
        ],
        'xAxis': [
            {'type': 'category', 'data': labels, 'axisLabel': {'show': False}},
            {'type': 'category', 'data': labels, 'gridIndex': 1},
        ],
        'yAxis': [{'scale': True}, lower_axis],
        'dataZoom': [
            {'type': 'inside', 'xAxisIndex': [0, 1], 'start': 40, 'end': 100},
            {'type': 'slider', 'xAxisIndex': [0, 1], 'bottom': 5, 'height': 20},
        ],
        'series': series,
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
