import indicators


def add_indicators(candles, settings):
    closes = candles['close']
    columns = {
        'rsi': indicators.rsi(closes, settings.rsi_period),
        'trend': indicators.trend(closes, settings.trend_period),
    }
    if settings.strategy == 'ma_cross':
        columns['fast'] = indicators.sma(closes, settings.ma_fast_period)
        columns['slow'] = indicators.sma(closes, settings.ma_slow_period)
    elif settings.strategy == 'bollinger':
        columns['lower'], columns['middle'], columns['upper'] = indicators.bollinger(
            closes, settings.bollinger_period, settings.bollinger_deviations,
        )
    elif settings.strategy == 'macd':
        columns['macd'], columns['macd_signal'] = indicators.macd(closes)
    return candles.assign(**columns)


def crossed_above(current, previous, line, other):
    return previous[line] <= previous[other] and current[line] > current[other]


def wants_to_buy(current, previous, settings):
    if settings.strategy == 'rsi':
        return current['rsi'] < settings.rsi_buy_below
    if settings.strategy == 'ma_cross':
        return crossed_above(current, previous, 'fast', 'slow')
    if settings.strategy == 'bollinger':
        return current['close'] < current['lower']
    if settings.strategy == 'macd':
        return crossed_above(current, previous, 'macd', 'macd_signal')
    return False


def wants_to_sell(current, previous, settings):
    if settings.strategy == 'rsi':
        return current['rsi'] > settings.rsi_sell_above
    if settings.strategy == 'ma_cross':
        return crossed_above(current, previous, 'slow', 'fast')
    if settings.strategy == 'bollinger':
        return current['close'] > current['middle']
    if settings.strategy == 'macd':
        return crossed_above(current, previous, 'macd_signal', 'macd')
    return False


def signal(current, previous, entry_price, settings):
    if entry_price is None:
        in_uptrend = settings.trend_period == 0 or current['close'] > current['trend']
        return 'buy' if in_uptrend and wants_to_buy(current, previous, settings) else None
    if settings.stop_loss_percent and current['close'] <= entry_price * (1 - settings.stop_loss_percent / 100):
        return 'stop_loss'
    if wants_to_sell(current, previous, settings):
        return 'sell'
    return None


def name(settings):
    if settings.strategy == 'rsi':
        return f'RSI {settings.rsi_buy_below:g}/{settings.rsi_sell_above:g}'
    if settings.strategy == 'ma_cross':
        return f'MA cross {settings.ma_fast_period}/{settings.ma_slow_period}'
    if settings.strategy == 'bollinger':
        return f'Bollinger {settings.bollinger_period}/{settings.bollinger_deviations:g}'
    return 'MACD 12/26/9'


def describe(row, settings):
    if settings.strategy == 'rsi':
        return f'RSI {row["rsi"]:.2f}'
    if settings.strategy == 'ma_cross':
        return f'fast MA {row["fast"]:,.2f} · slow MA {row["slow"]:,.2f}'
    if settings.strategy == 'bollinger':
        return f'lower {row["lower"]:,.2f} · middle {row["middle"]:,.2f} · upper {row["upper"]:,.2f}'
    return f'MACD {row["macd"]:.4f} · signal {row["macd_signal"]:.4f}'


def price_lines(settings):
    if settings.strategy == 'ma_cross':
        return [('fast', 'Fast MA'), ('slow', 'Slow MA')]
    if settings.strategy == 'bollinger':
        return [('upper', 'Upper band'), ('middle', 'Middle band'), ('lower', 'Lower band')]
    return []


def lower_panel(settings):
    if settings.strategy == 'macd':
        return [('macd', 'MACD'), ('macd_signal', 'MACD signal')], []
    return [('rsi', 'RSI')], [settings.rsi_buy_below, settings.rsi_sell_above]
