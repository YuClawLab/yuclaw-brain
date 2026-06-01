"""yuclaw/modules/execution_simulator.py — Paper trade with real bid/ask spread and slippage.

Simulates Level 2 execution: market orders cross the spread, limit orders
may not fill. Tracks slippage cost per trade and cumulative impact on returns.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class FillStatus(Enum):
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


@dataclass
class Order:
    """A simulated order."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    limit_price: Optional[float] = None
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class Fill:
    """Execution fill with slippage accounting."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    fill_price: float
    mid_price: float
    bid: float
    ask: float
    slippage_bps: float
    slippage_usd: float
    market_impact_bps: float
    status: FillStatus
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class Position:
    """Current position in a symbol."""
    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_slippage: float = 0.0
    num_trades: int = 0


@dataclass
class ExecutionReport:
    """Summary of all execution activity."""
    total_orders: int
    total_fills: int
    total_slippage_usd: float
    avg_slippage_bps: float
    total_volume_usd: float
    slippage_as_pct_of_volume: float
    positions: dict[str, Position]
    fills: list[Fill]

    def summary(self) -> str:
        lines = [
            "=" * 65,
            "  EXECUTION SIMULATOR — Paper Trading Report",
            "=" * 65,
            f"  Orders: {self.total_orders}  |  Fills: {self.total_fills}",
            f"  Total Volume: ${self.total_volume_usd:,.2f}",
            f"  Total Slippage: ${self.total_slippage_usd:,.2f} ({self.avg_slippage_bps:.1f} bps avg)",
            f"  Slippage as % of Volume: {self.slippage_as_pct_of_volume:.3%}",
            "",
            f"  {'Symbol':<8} {'Qty':>6} {'AvgCost':>10} {'RealPnL':>10} {'Slippage':>10} {'Trades':>6}",
            "  " + "-" * 55,
        ]
        for sym, pos in sorted(self.positions.items()):
            if pos.num_trades > 0:
                lines.append(
                    f"  {sym:<8} {pos.quantity:>6} ${pos.avg_cost:>9.2f} "
                    f"${pos.realized_pnl:>9.2f} ${pos.total_slippage:>9.2f} {pos.num_trades:>5}"
                )
        lines.append("=" * 65)
        return "\n".join(lines)


class ExecutionSimulator:
    """Paper trading engine with realistic execution simulation.

    Models:
    - Bid/ask spread crossing (market orders pay the spread)
    - Market impact (large orders move the price ~sqrt(size))
    - Slippage tracking per fill
    - Position management with average cost basis

    Spread model: spread_bps * price / 10000
    Market impact: impact_bps * sqrt(quantity / avg_volume) * price / 10000
    """

    def __init__(
        self,
        default_spread_bps: float = 5.0,
        market_impact_bps: float = 2.0,
        avg_daily_volume: int = 1_000_000,
    ):
        self._spread_bps = default_spread_bps
        self._impact_bps = market_impact_bps
        self._adv = avg_daily_volume
        self._positions: dict[str, Position] = {}
        self._fills: list[Fill] = []
        self._order_count = 0

    def _get_position(self, symbol: str) -> Position:
        if symbol not in self._positions:
            self._positions[symbol] = Position(symbol=symbol)
        return self._positions[symbol]

    def execute_market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        mid_price: float,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
    ) -> Fill:
        """Execute a market order with spread + market impact slippage.

        For BUY: fill at ask + market impact
        For SELL: fill at bid - market impact
        """
        self._order_count += 1
        order_id = f"ORD-{self._order_count:06d}"

        # Compute bid/ask if not provided
        half_spread = mid_price * self._spread_bps / 20000
        if bid is None:
            bid = mid_price - half_spread
        if ask is None:
            ask = mid_price + half_spread

        # Market impact: sqrt(participation_rate) * impact_coefficient
        import math
        participation = quantity / max(self._adv, 1)
        impact = mid_price * self._impact_bps / 10000 * math.sqrt(participation)

        if side == OrderSide.BUY:
            fill_price = ask + impact
        else:
            fill_price = bid - impact

        # Slippage = difference between fill and mid
        slippage = abs(fill_price - mid_price)
        slippage_bps = (slippage / mid_price) * 10000
        slippage_usd = slippage * quantity
        impact_bps = (impact / mid_price) * 10000

        fill = Fill(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            fill_price=round(fill_price, 4),
            mid_price=mid_price,
            bid=bid,
            ask=ask,
            slippage_bps=round(slippage_bps, 2),
            slippage_usd=round(slippage_usd, 2),
            market_impact_bps=round(impact_bps, 2),
            status=FillStatus.FILLED,
        )
        self._fills.append(fill)

        # Update position
        pos = self._get_position(symbol)
        pos.num_trades += 1
        pos.total_slippage += slippage_usd

        if side == OrderSide.BUY:
            total_cost = pos.avg_cost * pos.quantity + fill_price * quantity
            pos.quantity += quantity
            pos.avg_cost = total_cost / pos.quantity if pos.quantity > 0 else 0
        else:
            if pos.quantity >= quantity:
                pos.realized_pnl += (fill_price - pos.avg_cost) * quantity
                pos.quantity -= quantity
            else:
                # Short selling
                pos.quantity -= quantity

        return fill

    def get_report(self) -> ExecutionReport:
        """Generate execution summary."""
        total_volume = sum(f.fill_price * f.quantity for f in self._fills)
        total_slippage = sum(f.slippage_usd for f in self._fills)
        avg_bps = sum(f.slippage_bps for f in self._fills) / max(len(self._fills), 1)

        return ExecutionReport(
            total_orders=self._order_count,
            total_fills=len(self._fills),
            total_slippage_usd=round(total_slippage, 2),
            avg_slippage_bps=round(avg_bps, 2),
            total_volume_usd=round(total_volume, 2),
            slippage_as_pct_of_volume=total_slippage / max(total_volume, 1),
            positions=dict(self._positions),
            fills=self._fills,
        )

    def simulate_rebalance(
        self,
        target_weights: dict[str, float],
        prices: dict[str, float],
        total_capital: float = 1_000_000.0,
    ) -> ExecutionReport:
        """Simulate a full portfolio rebalance with realistic execution.

        Args:
            target_weights: {symbol: weight} where weights sum to ~1.0
            prices: {symbol: current_mid_price}
            total_capital: total portfolio value in USD

        Returns:
            ExecutionReport with all fills and slippage accounting.
        """
        for symbol, weight in target_weights.items():
            if symbol not in prices:
                continue

            price = prices[symbol]
            target_shares = int((weight * total_capital) / price)
            current = self._get_position(symbol).quantity
            delta = target_shares - current

            if delta > 0:
                self.execute_market_order(symbol, OrderSide.BUY, delta, price)
            elif delta < 0:
                self.execute_market_order(symbol, OrderSide.SELL, abs(delta), price)

        return self.get_report()
