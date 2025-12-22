require('dotenv').config()
const Binance = require('binance-api-node').default
const { RSI } = require('technicalindicators')

// Cliente Binance
const client = Binance({
  apiKey: process.env.BINANCE_API_KEY,
  apiSecret: process.env.BINANCE_API_SECRET,
  httpBase: 'https://testnet.binance.vision'
})

// CONFIGURACIÓN
const SYMBOL = 'XAIUSDT'
const INTERVAL = '1m'
const RSI_PERIOD = 14
const ORDER_SIZE = 10 // USDT
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
      console.log('COMPRANDO...')
      await client.order({
        symbol: SYMBOL,
        side: 'BUY',
        type: 'MARKET',
        quoteOrderQty: ORDER_SIZE
      })
      inPosition = true
    }

    if (lastRSI > 70 && inPosition) {
      console.log('VENDIENDO...')
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

// Ejecutar cada minuto
setInterval(trade, 60 * 1000)
