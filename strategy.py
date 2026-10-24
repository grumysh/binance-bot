def signal(rsi_value, in_position, settings):
    if not in_position and rsi_value < settings.rsi_buy_below:
        return 'buy'
    if in_position and rsi_value > settings.rsi_sell_above:
        return 'sell'
    return None
