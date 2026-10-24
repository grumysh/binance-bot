require('dotenv').config()
const Binance = require('binance-api-node').default
const { RSI } = require('technicalindicators')

if (!process.env.BINANCE_HTTP_BASE) {
  console.error('Missing BINANCE_HTTP_BASE in .env')
  process.exit(1)
}

const client = Binance({
  apiKey: process.env.BINANCE_API_KEY,
  apiSecret: process.env.BINANCE_API_SECRET,
  httpBase: process.env.BINANCE_HTTP_BASE
})

const SYMBOL = 'XAIUSDT'
const INTERVAL = '1m'
const RSI_PERIOD = 14
const ORDER_SIZE_USDT = 10
let inPosition = false

async function getCloses() {
  const candles = await client.candles({
    symbol: SYMBOL,
    interval: INTERVAL,
    limit: 100
  })
  return candles.map(c => Number(c.close))
}

async function trade() {
  try {
    const closes = await getCloses()

    const rsi = RSI.calculate({
      values: closes,
      period: RSI_PERIOD
    })

    const lastRSI = rsi[rsi.length - 1]
    console.log(`RSI: ${lastRSI}`)

    if (lastRSI < 30 && !inPosition) {
      console.log('BUYING...')
      await client.order({
        symbol: SYMBOL,
        side: 'BUY',
        type: 'MARKET',
        quoteOrderQty: ORDER_SIZE_USDT
      })
      inPosition = true
    }

    if (lastRSI > 70 && inPosition) {
      console.log('SELLING...')
      const balance = await client.accountInfo()
      const asset = SYMBOL.replace('USDT', '')

      const qty = balance.balances.find(b => b.asset === asset)?.free
      if (qty > 0) {
        await client.order({
          symbol: SYMBOL,
          side: 'SELL',
          type: 'MARKET',
          quantity: qty
        })
        inPosition = false
      }
    }

  } catch (err) {
    console.error('Error:', err.message)
  }
}

setInterval(trade, 60 * 1000)
