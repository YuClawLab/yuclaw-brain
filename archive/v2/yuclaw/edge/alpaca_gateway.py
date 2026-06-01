"""
Alpaca paper-trading broker — hand-rolled REST client.

Safety: constructor raises immediately if ALPACA_BASE_URL is not the paper
endpoint, and a validation ping (GET /v2/account) fails loudly on 401. Live
endpoints are explicitly prohibited.
"""
import os
from typing import Any

import requests

from .broker_gateway import BrokerGateway


PAPER_HOST = 'paper-api.alpaca.markets'
DATA_HOST = 'data.alpaca.markets'
DEFAULT_TIMEOUT = 10


class AlpacaGateway(BrokerGateway):
    """REST client targeting Alpaca's paper-trading API."""

    def __init__(self, validate: bool = True):
        self.api_key    = os.environ.get('ALPACA_API_KEY', '')
        self.secret_key = os.environ.get('ALPACA_SECRET_KEY', '')
        self.base_url   = os.environ.get('ALPACA_BASE_URL', '').rstrip('/')

        if not (self.api_key and self.secret_key):
            raise RuntimeError(
                'ALPACA_API_KEY or ALPACA_SECRET_KEY missing from environment. '
                'Source ~/.yuclaw_env with `set -a` and try again.')
        if PAPER_HOST not in self.base_url:
            raise RuntimeError(
                f'ALPACA_BASE_URL must point at {PAPER_HOST}. '
                f'Got: {self.base_url!r}. Live trading endpoints are prohibited.')

        self.headers = {
            'APCA-API-KEY-ID': self.api_key,
            'APCA-API-SECRET-KEY': self.secret_key,
        }
        if validate:
            self._validate_keys()

    def _validate_keys(self) -> None:
        """Ping /v2/account once. Fail loudly on 401 or any other error."""
        url = f'{self.base_url}/v2/account'
        r = requests.get(url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
        if r.status_code == 401:
            raise RuntimeError(
                'Alpaca returned 401 Unauthorized on validation ping. Verify '
                'ALPACA_API_KEY / ALPACA_SECRET_KEY in ~/.yuclaw_env match a '
                'valid paper-trading key pair at '
                'https://app.alpaca.markets/paper/dashboard/overview')
        if r.status_code >= 400:
            raise RuntimeError(
                f'Alpaca validation ping failed: HTTP {r.status_code} — '
                f'{r.text[:200]}')

    # --- BrokerGateway implementation ---

    def get_account(self) -> dict[str, Any]:
        r = requests.get(f'{self.base_url}/v2/account', headers=self.headers,
                         timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        d = r.json()
        return {
            'equity':            float(d.get('equity', 0)),
            'last_equity':       float(d.get('last_equity', 0)),
            'cash':              float(d.get('cash', 0)),
            'buying_power':      float(d.get('buying_power', 0)),
            'status':            d.get('status', 'UNKNOWN'),
            'pattern_day_trader': d.get('pattern_day_trader', False),
        }

    def get_clock(self) -> dict[str, Any]:
        r = requests.get(f'{self.base_url}/v2/clock', headers=self.headers,
                         timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        d = r.json()
        return {
            'is_open':    bool(d.get('is_open', False)),
            'next_open':  d.get('next_open', ''),
            'next_close': d.get('next_close', ''),
            'timestamp':  d.get('timestamp', ''),
        }

    def get_latest_price(self, ticker: str) -> float:
        url = f'https://{DATA_HOST}/v2/stocks/{ticker.upper()}/trades/latest'
        r = requests.get(url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        trade = r.json().get('trade', {})
        price = trade.get('p')
        if price is None:
            raise RuntimeError(f'No latest price available for {ticker}')
        return float(price)

    def get_positions(self) -> list[dict[str, Any]]:
        r = requests.get(f'{self.base_url}/v2/positions', headers=self.headers,
                         timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return [{
            'ticker':           p.get('symbol'),
            'qty':              int(float(p.get('qty', 0))),
            'avg_entry':        float(p.get('avg_entry_price', 0)),
            'current_price':    float(p.get('current_price', 0)),
            'market_value':     float(p.get('market_value', 0)),
            'unrealized_pl':    float(p.get('unrealized_pl', 0)),
            'unrealized_plpc':  float(p.get('unrealized_plpc', 0)),
        } for p in r.json()]

    def get_orders(self, status: str = 'all', limit: int = 10) -> list[dict[str, Any]]:
        r = requests.get(f'{self.base_url}/v2/orders',
                         params={'status': status, 'limit': limit},
                         headers=self.headers, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return [{
            'id':               o.get('id'),
            'ticker':           o.get('symbol'),
            'side':             o.get('side'),
            'qty':              int(float(o.get('qty', 0))),
            'status':           o.get('status'),
            'filled_qty':       int(float(o.get('filled_qty', 0))),
            'filled_avg_price': float(o.get('filled_avg_price') or 0),
            'submitted_at':     o.get('submitted_at', ''),
        } for o in r.json()]

    def submit_market_order(self, ticker: str, side: str, qty: int) -> dict[str, Any]:
        side = side.lower()
        if side not in ('buy', 'sell'):
            raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
        payload = {
            'symbol':        ticker.upper(),
            'qty':           str(qty),
            'side':          side,
            'type':          'market',
            'time_in_force': 'day',
        }
        r = requests.post(f'{self.base_url}/v2/orders', json=payload,
                          headers=self.headers, timeout=DEFAULT_TIMEOUT)
        if not r.ok:
            raise RuntimeError(
                f'Order rejected by Alpaca: HTTP {r.status_code} — {r.text[:200]}')
        o = r.json()
        return {
            'id':           o.get('id'),
            'ticker':       o.get('symbol'),
            'side':         o.get('side'),
            'qty':          int(float(o.get('qty', 0))),
            'status':       o.get('status'),
            'submitted_at': o.get('submitted_at', ''),
        }

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        r = requests.delete(f'{self.base_url}/v2/orders/{order_id}',
                            headers=self.headers, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return {'id': order_id, 'cancelled': True}

    def liquidate_all(self) -> list[dict[str, Any]]:
        r = requests.delete(f'{self.base_url}/v2/positions', headers=self.headers,
                            timeout=DEFAULT_TIMEOUT)
        if r.status_code not in (200, 207):
            raise RuntimeError(
                f'liquidate_all failed: HTTP {r.status_code} — {r.text[:200]}')
        try:
            return r.json()
        except Exception:
            return []
