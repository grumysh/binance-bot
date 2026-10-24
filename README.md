# Binance Bot

A simple RSI trading bot for Binance Spot. It runs on the **Binance Spot testnet** by default, so it trades with fake
funds unless you explicitly switch it to the real exchange.

## Tech stack

- **Python 3.15**
- **[uv](https://docs.astral.sh/uv/)** for the Python version, virtual environment and dependencies
- **[ccxt](https://github.com/ccxt/ccxt)** to talk to Binance
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** to load the API keys from `.env`

## How it works

Every minute the bot:

1. Downloads the last 100 one-minute candles for the selected symbol (`BTC/USDT` by default).
2. Calculates the 14-period RSI from the closing prices.
3. **Buys** 10 USDT worth of the coin at market price when the RSI drops below 30 and it has no open position.
4. **Sells** only the amount it bought, at market price, when the RSI goes above 70 and it has an open position. The
   amount is rounded to the step size Binance accepts.

The available symbols and the default settings (symbol, candle interval, RSI period, buy and sell levels, order size)
live in `settings.py`.

| Symbol | Notes |
|---|---|
| `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `BNB/USDT`, `XRP/USDT`, `DOGE/USDT` | Highest volume, they move on the testnet |

### Limitations

- The open position is kept in memory only. If the bot restarts while holding a coin, it won't sell it.
- There is no stop loss.
- The RSI uses the current candle, which is still open, so the signal can change within the same minute.

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

## Disclaimer

This is a learning project, not financial advice. A 30/70 RSI strategy on one-minute candles usually loses money once
trading fees are included. Don't run it with real funds.
