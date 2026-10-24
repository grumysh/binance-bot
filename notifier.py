import json
import logging
import os
import urllib.request

from dotenv import load_dotenv

from market import testnet

load_dotenv()

log = logging.getLogger('bot')


def channels():
    configured = []
    if os.getenv('DISCORD_WEBHOOK_URL'):
        configured.append('Discord')
    if os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'):
        configured.append('Telegram')
    return configured


def post_json(url, data):
    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': 'binance-bot'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()


def send(message):
    text = f'[{"TESTNET" if testnet else "REAL ACCOUNT"}] {message}'
    sent = []
    if 'Discord' in channels():
        try:
            post_json(os.getenv('DISCORD_WEBHOOK_URL'), {'content': text})
            sent.append('Discord')
        except Exception:
            log.exception('Could not send the Discord notification')
    if 'Telegram' in channels():
        try:
            url = f'https://api.telegram.org/bot{os.getenv("TELEGRAM_BOT_TOKEN")}/sendMessage'
            post_json(url, {'chat_id': os.getenv('TELEGRAM_CHAT_ID'), 'text': text})
            sent.append('Telegram')
        except Exception:
            log.exception('Could not send the Telegram notification')
    return sent
