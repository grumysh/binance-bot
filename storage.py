import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'bot.db'


def connect(path=DB_PATH):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    with db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL NOT NULL,
                cost REAL NOT NULL,
                fee REAL NOT NULL,
                fee_currency TEXT,
                testnet INTEGER NOT NULL,
                order_id TEXT
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT NOT NULL,
                testnet INTEGER NOT NULL,
                amount REAL NOT NULL,
                entry_price REAL NOT NULL,
                cost REAL NOT NULL,
                opened_at TEXT NOT NULL,
                PRIMARY KEY (symbol, testnet)
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                time INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                PRIMARY KEY (symbol, interval, time)
            )
        ''')
    return db


def insert_trade(db, order, side, amount, testnet):
    fees = order.get('fees') or []
    db.execute(
        '''
        INSERT INTO trades (time, symbol, side, amount, price, cost, fee, fee_currency, testnet, order_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            order['datetime'],
            order['symbol'],
            side,
            amount,
            order['average'],
            order['cost'],
            sum(fee['cost'] for fee in fees),
            fees[0]['currency'] if fees else None,
            testnet,
            order['id'],
        ),
    )


def get_position(db, symbol, testnet):
    return db.execute('SELECT * FROM positions WHERE symbol = ? AND testnet = ?', (symbol, testnet)).fetchone()


def record_buy(db, order, amount, testnet):
    with db:
        insert_trade(db, order, 'buy', amount, testnet)
        db.execute(
            'INSERT INTO positions (symbol, testnet, amount, entry_price, cost, opened_at) VALUES (?, ?, ?, ?, ?, ?)',
            (order['symbol'], testnet, amount, order['average'], order['cost'], order['datetime']),
        )


def record_sell(db, order, testnet):
    with db:
        insert_trade(db, order, 'sell', order['filled'], testnet)
        db.execute('DELETE FROM positions WHERE symbol = ? AND testnet = ?', (order['symbol'], testnet))


def save_candles(db, symbol, interval, candles):
    with db:
        db.executemany(
            'INSERT OR IGNORE INTO candles (symbol, interval, time, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [(symbol, interval, *candle) for candle in candles],
        )


def candle_range(db, symbol, interval):
    return db.execute('SELECT MIN(time), MAX(time) FROM candles WHERE symbol = ? AND interval = ?', (symbol, interval)).fetchone()


def load_candles(db, symbol, interval, since):
    return db.execute(
        'SELECT * FROM candles WHERE symbol = ? AND interval = ? AND time >= ? ORDER BY time',
        (symbol, interval, since),
    ).fetchall()
