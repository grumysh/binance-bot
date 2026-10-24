import argparse
from dataclasses import replace

import history
import indicators
import storage
import strategy
from settings import SYMBOLS, Settings

exchange = history.exchange


def simulate(candles, settings, fee_rate):
    exchange.load_markets()
    candles = candles.assign(rsi=indicators.rsi(candles['close'], settings.rsi_period))
    rows = list(candles.itertuples())

    trades = []
    position = None
    leftover = 0.0

    for current, following in zip(rows, rows[1:]):
        action = strategy.signal(current.rsi, position is not None, settings)
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
            amount = float(exchange.amount_to_precision(settings.symbol, position['amount']))
            leftover += position['amount'] - amount
            proceeds = amount * price
            fee = proceeds * fee_rate
            trades.append({
                **position,
                'exit_time': following.Index,
                'exit_price': price,
                'proceeds': proceeds - fee,
                'fees': position['fees'] + fee,
                'profit': proceeds - fee - position['cost'],
            })
            position = None

    return {
        'trades': trades,
        'open_position': position,
        'leftover': leftover,
        'last_price': rows[-1].close,
        'first_price': rows[0].close,
    }


def print_summary(result, settings, fee_rate):
    trades = result['trades']
    last_price = result['last_price']
    closed_profit = sum(trade['profit'] for trade in trades)
    fees = sum(trade['fees'] for trade in trades)
    leftover_value = result['leftover'] * last_price
    position = result['open_position']
    open_profit = position['amount'] * last_price - position['cost'] if position else 0.0
    total = closed_profit + leftover_value + open_profit
    buy_and_hold = (last_price / result['first_price'] - 1) * 100

    print(f'{settings.symbol} {settings.interval} | RSI {settings.rsi_period} buy < {settings.rsi_buy_below} '
          f'sell > {settings.rsi_sell_above} | {settings.order_size_usdt} USDT per trade | fee {fee_rate * 100}%')
    print(f'Closed trades:        {len(trades)}')
    print(f'Profit closed trades: {closed_profit:+.2f} USDT')
    print(f'Fees paid:            {fees:.2f} USDT')
    print(f'Unsold leftover coin: {leftover_value:.2f} USDT')
    print(f'Open position:        {open_profit:+.2f} USDT' if position else 'Open position:        none')
    print(f'Total:                {total:+.2f} USDT ({total / settings.order_size_usdt * 100:+.1f}% of the order size)')
    print(f'Buy and hold:         {buy_and_hold:+.1f}%')


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
