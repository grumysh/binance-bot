# Binance Bot

A simple RSI trading bot for Binance Spot. It runs on the **Binance Spot testnet** by default, so it trades with fake
funds unless you explicitly switch it to the real exchange.

## Tech stack

- **Python 3.15**
- **[uv](https://docs.astral.sh/uv/)** for the Python version, virtual environment and dependencies
- **[ccxt](https://github.com/ccxt/ccxt)** to talk to Binance
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** to load the API keys from `.env`
- **[pandas](https://pandas.pydata.org/)** to work with candles and calculate the indicators (`indicators.py`)
- **SQLite** to store trades and open positions

## How it works

Every time a candle closes, the bot:

1. Downloads the last closed one-minute candles for the selected symbol (`BTC/USDT` by default).
2. Calculates the 14-period RSI from the closing prices.
3. **Buys** 10 USDT worth of the coin at market price when the RSI drops below 30 and it has no open position.
4. **Sells** only the amount it bought, at market price, when the RSI goes above 70 and it has an open position. The
   amount is rounded to the step size Binance accepts.

The available symbols and the default settings (symbol, candle interval, RSI period, buy and sell levels, order size)
live in `settings.py`.

| Symbol | Notes |
|---|---|
| `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `BNB/USDT`, `XRP/USDT`, `DOGE/USDT` | Highest volume, they move on the testnet |

### Data

The bot keeps its data in a SQLite file, `bot.db`, created next to `bot.py` on the first run:

| Table | Contents |
|---|---|
| `trades` | Every buy and sell: time, symbol, side, amount, price, cost, fee, testnet or real, Binance order id |
| `positions` | The open position per symbol and account (testnet or real), so the bot picks it up again after a restart |
| `candles` | Historical candles from the real Binance market, used for backtesting |

You can open it with [DB Browser for SQLite](https://sqlitebrowser.org/).

### Limitations

- There is no stop loss.

## Running it

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

uv downloads the right Python version automatically the first time the bot runs.

### 2. Get testnet API keys

1. Go to [testnet.binance.vision](https://testnet.binance.vision/) and log in with GitHub.
2. Generate an **HMAC-SHA-256** key and copy the API key and secret.

### 3. Configure the environment

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Description |
|---|---|
| `BINANCE_API_KEY` | Binance API key |
| `BINANCE_API_SECRET` | Binance API secret |
| `BINANCE_TESTNET` | `true` to use the testnet (default). Set it to `false` only to trade with real money. |

### 4. Start the bot

```bash
uv run bot.py
```

Stop it with `Ctrl+C`.

### 5. Download historical candles

```bash
uv run history.py --symbol BTC/USDT --interval 1m --days 30
```

The candles come from the real Binance market (no API keys needed) and are saved in `bot.db`. Running it again only
downloads the candles that are missing. All three options are optional and default to the values in `settings.py`
and 30 days.

### 6. Backtest the strategy

```bash
uv run backtest.py --symbol BTC/USDT --interval 1m --days 30 --fee 0.1
```

It downloads any missing candles and replays the strategy on them, buying and selling at the open of the candle after
each signal, with Binance's rounding and the given fee per trade (0.1% by default). It prints the profit of the closed
trades, the fees paid, the value of the coin left unsold after rounding, the open position and a buy and hold
comparison.

### Logs

Everything the bot does (RSI on each candle, buys, sells and errors) is printed to the console and saved to
`logs/bot.log`. The file rotates at midnight and the last 30 days are kept.

## Disclaimer

This is a learning project, not financial advice. A 30/70 RSI strategy on one-minute candles usually loses money once
trading fees are included. Don't run it with real funds.
