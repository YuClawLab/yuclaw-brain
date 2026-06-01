"""
YUCLAW broker abstraction.

BrokerGateway is the abstract contract. AlpacaGateway is the first concrete
implementation; future RobinhoodGateway / IBGateway can inherit the same
interface and slot into the yuclaw paper / yuclaw live (future) commands
without changing call sites.
"""
import abc
from typing import Any


class BrokerGateway(abc.ABC):
    """Abstract broker interface for yuclaw."""

    @abc.abstractmethod
    def get_account(self) -> dict[str, Any]:
        """Account summary. Required keys: equity, last_equity, cash, buying_power."""
        ...

    @abc.abstractmethod
    def get_clock(self) -> dict[str, Any]:
        """Market clock. Required keys: is_open, next_open, next_close."""
        ...

    @abc.abstractmethod
    def get_latest_price(self, ticker: str) -> float:
        """Latest trade price for a ticker. Raises on lookup failure."""
        ...

    @abc.abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        """Open positions with ticker, qty, avg_entry, current_price, unrealized_pl."""
        ...

    @abc.abstractmethod
    def get_orders(self, status: str = 'all', limit: int = 10) -> list[dict[str, Any]]:
        """Recent orders."""
        ...

    @abc.abstractmethod
    def submit_market_order(self, ticker: str, side: str, qty: int) -> dict[str, Any]:
        """Submit a market order. side is 'buy' or 'sell'."""
        ...

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a pending order."""
        ...

    @abc.abstractmethod
    def liquidate_all(self) -> list[dict[str, Any]]:
        """Emergency liquidate all open positions."""
        ...
