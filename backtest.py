import argparse
from dataclasses import replace

import pandas as pd

import history
import indicators
import storage
import strategy
from settings import SYMBOLS, Settings

exchange = history.exchange


def simulate(candles, settings, fee_rate):
    exchange.load_markets()
    candles = candles.assign(
        rsi=indicators.rsi(candles['close'], settings.rsi_period),
        trend=indicators.trend(candles['close'], settings.trend_period),
    )
    rows = list(candles.itertuples())

    trades = []
    position = None
    leftover = 0.0

    for current, following in zip(rows, rows[1:]):
        action = strategy.signal(current.rsi, current.close, current.trend, position is not None, settings)
        price = following.open

        if action == 'buy':
            amount = float(exchange.amount_to_precision(settings.symbol, settings.order_size_usdt / price))
            fee = amount * fee_rate
            position = {
                'entry_time': following.Index,
                'entry_price': price,
                'amount': amount - fee,
                'cost': amount * price,
                'fees': fee * price,
            }

        elif action == 'sell':
            previous_leftover = leftover
            available = position['amount'] + leftover
            amount = float(exchange.amount_to_precision(settings.symbol, available))
            leftover = available - amount
            proceeds = amount * price
            fee = proceeds * fee_rate
            trades.append({
                **position,
                'exit_time': following.Index,
                'exit_price': price,
                'proceeds': proceeds - fee,
                'fees': position['fees'] + fee,
                'profit': proceeds - fee - position['cost'] + (leftover - previous_leftover) * price,
            })
            position = None

    return {
        'trades': trades,
        'open_position': position,
        'leftover': leftover,
        'last_price': rows[-1].close,
        'first_price': rows[0].close,
    }


def metrics(result, settings):
    trades = pd.DataFrame(result['trades'], columns=['entry_time', 'exit_time', 'profit', 'fees'])
    last_price = result['last_price']
    position = result['open_position']

    profit = trades['profit']
    wins = profit[profit > 0]
    losses = profit[profit <= 0]
    cumulative = profit.cumsum()
    drawdown = (cumulative.cummax().clip(lower=0) - cumulative).max() if len(trades) else 0.0

    closed_profit = profit.sum()
    leftover_value = result['leftover'] * last_price
    open_profit = position['amount'] * last_price - position['cost'] if position else 0.0
    total = closed_profit + open_profit

    return {
        'trades': len(trades),
        'win_rate': len(wins) / len(trades) * 100 if len(trades) else 0.0,
        'average_win': wins.mean() if len(wins) else 0.0,
        'average_loss': losses.mean() if len(losses) else 0.0,
        'best_trade': profit.max() if len(trades) else 0.0,
        'worst_trade': profit.min() if len(trades) else 0.0,
        'profit_factor': wins.sum() / -losses.sum() if losses.sum() < 0 else float('inf'),
        'max_drawdown': drawdown,
        'average_duration': (trades['exit_time'] - trades['entry_time']).mean() if len(trades) else pd.Timedelta(0),
        'closed_profit': closed_profit,
        'fees': trades['fees'].sum(),
        'leftover_value': leftover_value,
        'open_profit': open_profit if position else None,
        'total': total,
        'total_percent': total / settings.order_size_usdt * 100,
        'buy_and_hold_percent': (last_price / result['first_price'] - 1) * 100,
    }


def print_summary(result, settings, fee_rate):
    m = metrics(result, settings)
    open_position = f'{m["open_profit"]:+.2f} USDT' if m['open_profit'] is not None else 'none'
    duration = str(m['average_duration'].round('1min')).replace('0 days ', '')

    print(f'{settings.symbol} {settings.interval} | RSI {settings.rsi_period} buy < {settings.rsi_buy_below} '
          f'sell > {settings.rsi_sell_above} | trend filter {settings.trend_period or "off"} '
          f'| {settings.order_size_usdt} USDT per trade | fee {fee_rate * 100}%')
    print()
    print(f'Closed trades:        {m["trades"]}')
    print(f'Win rate:             {m["win_rate"]:.1f}%')
    print(f'Average win:          {m["average_win"]:+.4f} USDT')
    print(f'Average loss:         {m["average_loss"]:+.4f} USDT')
    print(f'Best trade:           {m["best_trade"]:+.4f} USDT')
    print(f'Worst trade:          {m["worst_trade"]:+.4f} USDT')
    print(f'Profit factor:        {m["profit_factor"]:.2f}')
    print(f'Max drawdown:         {m["max_drawdown"]:.2f} USDT')
    print(f'Average duration:     {duration}')
    print()
    print(f'Profit closed trades: {m["closed_profit"]:+.2f} USDT')
    print(f'Fees paid:            {m["fees"]:.2f} USDT')
    print(f'Unsold leftover coin: {m["leftover_value"]:.2f} USDT (already counted in the trades)')
    print(f'Open position:        {open_position}')
    print(f'Total:                {m["total"]:+.2f} USDT ({m["total_percent"]:+.1f}% of the order size)')
    print(f'Buy and hold:         {m["buy_and_hold_percent"]:+.1f}%')


if __name__ == '__main__':
    defaults = Settings()
    parser = argparse.ArgumentParser(description='Simulate the strategy on historical candles')
    parser.add_argument('--symbol', default=defaults.symbol, choices=SYMBOLS)
    parser.add_argument('--interval', default=defaults.interval)
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--fee', type=float, default=0.1, help='Fee per trade in percent')
    args = parser.parse_args()

    settings = replace(defaults, symbol=args.symbol, interval=args.interval)
    fee_rate = args.fee / 100
    db = storage.connect()
    history.download_candles(db, settings.symbol, settings.interval, args.days)
    since = exchange.milliseconds() - args.days * history.DAY_MS
    candles = indicators.candles_frame(storage.load_candles(db, settings.symbol, settings.interval, since))
    print_summary(simulate(candles, settings, fee_rate), settings, fee_rate)
