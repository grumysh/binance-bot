from dataclasses import dataclass

SYMBOLS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'BNB/USDT',
    'XRP/USDT',
    'DOGE/USDT',
]


@dataclass
class Settings:
    symbol: str = 'BTC/USDT'
    interval: str = '1h'
    rsi_period: int = 14
    rsi_buy_below: float = 30
    rsi_sell_above: float = 70
    trend_period: int = 200
    order_size_usdt: float = 10

    def __post_init__(self):
        if self.symbol not in SYMBOLS:
            raise ValueError(f'{self.symbol} is not in the available symbols: {", ".join(SYMBOLS)}')
