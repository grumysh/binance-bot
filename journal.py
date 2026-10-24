from datetime import datetime

import pandas as pd


def fee_in_usdt(trade):
    if trade['fee_currency'] == 'USDT':
        return trade['fee']
    return trade['fee'] * trade['price']


def journal(trades):
    last_buy = {}
    rows = []
    for trade in trades:
        row = dict(trade)
        row['fee_usdt'] = fee_in_usdt(trade)
        row['profit'] = None
        row['profit_percent'] = None
        if trade['side'] == 'buy':
            last_buy[trade['symbol']] = trade
        elif trade['symbol'] in last_buy:
            buy = last_buy.pop(trade['symbol'])
            cost = trade['amount'] * buy['cost'] / buy['amount']
            row['profit'] = trade['cost'] - row['fee_usdt'] - cost
            row['profit_percent'] = row['profit'] / cost * 100
        rows.append(row)
    return rows


def summary(rows):
    profits = [row['profit'] for row in rows if row['profit'] is not None]
    return {
        'closed': len(profits),
        'win_rate': sum(profit > 0 for profit in profits) / len(profits) * 100 if profits else 0.0,
        'profit': sum(profits),
        'fees': sum(row['fee_usdt'] for row in rows),
    }


def local_time(iso_time):
    return pd.Timestamp(iso_time).tz_convert(datetime.now().astimezone().tzinfo).strftime('%Y-%m-%d %H:%M')
