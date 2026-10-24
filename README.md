# Binance Bot

A simple RSI trading bot for Binance Spot. It runs on the **Binance Spot testnet** by default, so it trades with fake
funds unless you explicitly switch it to the real exchange.

## Tech stack

- **Python 3.14**
- **[uv](https://docs.astral.sh/uv/)** for the Python version, virtual environment and dependencies
- **[ccxt](https://github.com/ccxt/ccxt)** to talk to Binance
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** to load the API keys from `.env`
- **[pandas](https://pandas.pydata.org/)** to work with candles and calculate the indicators (`indicators.py`)
- **SQLite** to store trades and open positions
- **[NiceGUI](https://nicegui.io/)** for the graphical interface

## How it works

Every time a candle closes, the bot:

1. Downloads the last closed candles for the selected symbol and interval (`BTC/USDT` and one hour by default).
2. Calculates the 14-period RSI from the closing prices.
3. **Buys** 10 USDT worth of the coin at market price when the strategy says so and it has no open position. If the
   trend filter is on (`trend_period` in `settings.py`, 200 by default), it only buys while the price is above the
   average of the last `trend_period` candles, so it doesn't buy into a falling market.
4. **Sells** only the amount it bought, at market price, when the strategy says so and it has an open position. The
   amount is rounded to the step size Binance accepts.
5. If the stop loss is on (`stop_loss_percent`, off by default), it also sells when a candle closes that percentage
   below the buy price. It is checked at the candle close, so the real loss can be bigger than the percentage.

### Strategies

| Strategy | Buys when | Sells when |
|---|---|---|
| **RSI** (default, 30/70) | The RSI drops below the buy level | The RSI goes above the sell level |
| **Moving average cross** (20/50) | The fast average crosses above the slow one | The fast average crosses below the slow one |
| **Bollinger bands** (20 candles, 2 deviations) | The price closes below the lower band | The price closes above the middle band |
| **MACD** (12/26/9) | The MACD line crosses above its signal line | The MACD line crosses below its signal line |

The trend filter and the stop loss work with every strategy.

The available symbols and the default settings (symbol, candle interval, strategy and its parameters, trend filter,
stop loss, order size)
live in `settings.py`. You can change them from the app while the bot is stopped; they are validated and saved in
`bot.db`, and both `app.py` and `bot.py` use the saved settings.

| Symbol | Notes |
|---|---|
| `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `BNB/USDT`, `XRP/USDT`, `DOGE/USDT` | Highest volume, they move on the testnet |

### Data

The bot keeps its data in a SQLite file, `bot.db`, created next to `bot.py` on the first run:

| Table | Contents |
|---|---|
| `trades` | Every buy and sell: time, symbol, side, amount, price, cost, fee, testnet or real, Binance order id |
| `positions` | The open position per symbol and account (testnet or real), so the bot picks it up again after a restart |
| `settings` | The settings saved from the app |
| `leftovers` | Coin left unsold after Binance's rounding, added to the next sell so it never piles up |
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

With the graphical interface:

```bash
uv run app.py
```

Then open [http://localhost:8080](http://localhost:8080) and use **Start** and **Stop**. The page also shows the
current price, the RSI of the last closed candle, whether the price is above the trend filter, your USDT and coin
balances, what the strategy would do now and the open position with its profit or loss, refreshed every 15 seconds.
Below it, a candlestick chart of the last 150 candles shows the trend line, the bot's buys and sells and the RSI with
its buy and sell levels. At the bottom, the trades table lists every buy and sell of the current account (testnet or
real) with its fee and, for each sell, the result after fees compared with the cost of the amount sold, plus a summary
and a search box.

The **Backtest** page runs the same backtest and comparison as `backtest.py` and `compare.py` from the browser: pick
the settings, the days of history and the fee, then see the metrics, the chart with the simulated buys and sells, the
accumulated result and every simulated trade. The comparison table loads a configuration into the form with one click,
and **Use these settings in the bot** saves it for the bot. Closing the browser tab doesn't
stop the bot; stopping `app.py` does.

Or only in the console:

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
each signal, with Binance's rounding and the given fee per trade (0.1% by default). It prints:

| Metric | Meaning |
|---|---|
| Win rate | Percentage of closed trades with a profit |
| Average win / loss | Average profit of the winning and of the losing trades |
| Best / worst trade | Biggest single profit and loss |
| Profit factor | Total won divided by total lost. Above 1 the strategy makes money |
| Max drawdown | Biggest drop of the accumulated profit from its highest point |
| Average duration | Average time between a buy and its sell |
| Total | Profit of the closed trades plus the open position, compared with buying and holding |

### 7. Compare configurations

```bash
uv run compare.py --symbols BTC/USDT ETH/USDT --days 180 --fee 0.1
```

It backtests every combination of candle interval (5m, 15m, 1h, 4h), strategy (RSI 20/80, 25/75, 30/70 and 35/65,
moving average cross, Bollinger bands and MACD) and trend filter (off, 100, 200) for the given symbols and prints a table sorted by total profit. A configuration that wins on one period can lose on
another, so check the best ones on a different period before trusting them.

### Logs

Everything the bot does (RSI on each candle, buys, sells and errors) is printed to the console and saved to
`logs/bot.log`. The file rotates at midnight and the last 30 days are kept.

## Disclaimer

This is a learning project, not financial advice. A 30/70 RSI strategy on short candles loses money once trading fees
are included, and even the default settings only look good on past data, with few trades. Don't run it with real
funds.
