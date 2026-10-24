def signal(rsi_value, close, trend_value, in_position, settings):
    in_uptrend = settings.trend_period == 0 or close > trend_value
    if not in_position and rsi_value < settings.rsi_buy_below and in_uptrend:
        return 'buy'
    if in_position and rsi_value > settings.rsi_sell_above:
        return 'sell'
    return None
