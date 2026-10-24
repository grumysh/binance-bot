import argparse
from dataclasses import asdict, replace

import pandas as pd

import backtest
import history
import indicators
import storage
import strategy
from settings import SYMBOLS, Settings

INTERVALS = ['5m', '15m', '1h', '4h']
TREND_PERIODS = [0, 100, 200]
VARIANTS = [
    *[{'strategy': 'rsi', 'rsi_buy_below': buy, 'rsi_sell_above': sell} for buy, sell in [(20, 80), (25, 75), (30, 70), (35, 65)]],
    {'strategy': 'ma_cross'},
    {'strategy': 'bollinger'},
    {'strategy': 'macd'},
]
CONFIGURATIONS = len(INTERVALS) * len(TREND_PERIODS) * len(VARIANTS)


def compare(db, symbols, days, fee_rate, base=None):
    base = base or Settings()
    since = history.exchange.milliseconds() - days * history.DAY_MS
    rows = []
    for symbol in symbols:
        for interval in INTERVALS:
            history.download_candles(db, symbol, interval, days)
            candles = indicators.candles_frame(storage.load_candles(db, symbol, interval, since))
            for variant in VARIANTS:
                for trend_period in TREND_PERIODS:
                    settings = replace(base, symbol=symbol, interval=interval, trend_period=trend_period, **variant)
                    m = backtest.metrics(backtest.simulate(candles, settings, fee_rate), settings)
                    rows.append({
                        'symbol': symbol,
                        'interval': interval,
                        'strategy': strategy.name(settings),
                        'trend': trend_period or 'off',
                        'trades': m['trades'],
                        'win %': round(m['win_rate'], 1),
                        'profit factor': round(m['profit_factor'], 2),
                        'max drawdown': round(m['max_drawdown'], 2),
                        'avg duration': m['average_duration'].round('1h'),
                        'total USDT': round(m['total'], 2),
                        'total %': round(m['total_percent'], 1),
                        'buy and hold %': round(m['buy_and_hold_percent'], 1),
                        'settings': asdict(settings),
                    })
    return pd.DataFrame(rows).sort_values('total USDT', ascending=False, ignore_index=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compare intervals, strategies and trend filters on historical candles')
    parser.add_argument('--symbols', nargs='+', default=[Settings().symbol], choices=SYMBOLS)
    parser.add_argument('--days', type=int, default=180)
    parser.add_argument('--fee', type=float, default=0.1, help='Fee per trade in percent')
    args = parser.parse_args()

    results = compare(storage.connect(), args.symbols, args.days, args.fee / 100)
    with pd.option_context('display.max_rows', None, 'display.width', 200):
        print(results.drop(columns='settings').to_string())
