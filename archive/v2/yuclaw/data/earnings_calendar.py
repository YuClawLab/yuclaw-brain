"""Earnings Calendar — upcoming earnings dates from real data."""
import yfinance as yf
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class EarningsEvent:
    ticker: str
    company: str
    earnings_date: Optional[str]
    days_until: Optional[int]
    eps_estimate: Optional[float] = None
    is_real: bool = True


class EarningsCalendar:
    def get_upcoming(self, tickers: list[str], days_ahead: int = 30) -> list[EarningsEvent]:
        events = []
        for t in tickers:
            try:
                info = yf.Ticker(t).info
                name = info.get("shortName", t)
                cal = yf.Ticker(t).calendar
                if cal is not None and not cal.empty:
                    dates = cal.get("Earnings Date", [])
                    if len(dates) > 0:
                        ed = str(dates[0])[:10]
                        dt = datetime.strptime(ed, "%Y-%m-%d")
                        days = (dt - datetime.now()).days
                        if 0 <= days <= days_ahead:
                            events.append(EarningsEvent(
                                ticker=t, company=name, earnings_date=ed,
                                days_until=days, eps_estimate=info.get("forwardEps"),
                            ))
            except Exception:
                pass
        return sorted(events, key=lambda x: x.days_until or 999)
