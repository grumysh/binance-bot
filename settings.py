from dataclasses import dataclass, fields

SYMBOLS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'BNB/USDT',
    'XRP/USDT',
    'DOGE/USDT',
]

INTERVALS = ['1m', '5m', '15m', '1h', '4h']

STRATEGIES = {
    'rsi': 'RSI',
    'ma_cross': 'Moving average cross',
    'bollinger': 'Bollinger bands',
    'macd': 'MACD',
}

MIN_ORDER_USDT = 5


@dataclass
class Settings:
    symbol: str = 'BTC/USDT'
    interval: str = '1h'
    strategy: str = 'rsi'
    rsi_period: int = 14
    rsi_buy_below: float = 30
    rsi_sell_above: float = 70
    ma_fast_period: int = 20
    ma_slow_period: int = 50
    bollinger_period: int = 20
    bollinger_deviations: float = 2
    trend_period: int = 200
    stop_loss_percent: float = 0
    daily_loss_limit_usdt: float = 0
    order_size_usdt: float = 10

    def __post_init__(self):
        if self.symbol not in SYMBOLS:
            raise ValueError(f'{self.symbol} is not in the available symbols: {", ".join(SYMBOLS)}')
        if self.interval not in INTERVALS:
            raise ValueError(f'{self.interval} is not in the available intervals: {", ".join(INTERVALS)}')
        if self.strategy not in STRATEGIES:
            raise ValueError(f'{self.strategy} is not in the available strategies: {", ".join(STRATEGIES)}')
        if not 2 <= self.ma_fast_period < self.ma_slow_period:
            raise ValueError('The fast moving average must be at least 2 and shorter than the slow one')
        if self.bollinger_period < 2 or self.bollinger_deviations <= 0:
            raise ValueError('The Bollinger period must be at least 2 and the deviations more than 0')
        if self.rsi_period < 2:
            raise ValueError('The RSI period must be at least 2')
        if not 0 < self.rsi_buy_below < self.rsi_sell_above < 100:
            raise ValueError('The RSI levels must be between 0 and 100, with the buy level below the sell level')
        if self.trend_period < 0:
            raise ValueError('The trend period must be 0 (off) or more')
        if not 0 <= self.stop_loss_percent < 100:
            raise ValueError('The stop loss must be between 0 (off) and 100%')
        if self.daily_loss_limit_usdt < 0:
            raise ValueError('The daily loss limit must be 0 (off) or more')
        if self.order_size_usdt < MIN_ORDER_USDT:
            raise ValueError(f'The order size must be at least {MIN_ORDER_USDT} USDT, the Binance minimum')

    @classmethod
    def from_dict(cls, data):
        names = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in names})
