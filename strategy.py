def signal(rsi_value, close, trend_value, entry_price, settings):
    in_position = entry_price is not None
    in_uptrend = settings.trend_period == 0 or close > trend_value
    if not in_position and rsi_value < settings.rsi_buy_below and in_uptrend:
        return 'buy'
    if in_position and settings.stop_loss_percent and close <= entry_price * (1 - settings.stop_loss_percent / 100):
        return 'stop_loss'
    if in_position and rsi_value > settings.rsi_sell_above:
        return 'sell'
    return None
