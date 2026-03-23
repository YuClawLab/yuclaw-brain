"""Financial NER — pattern-based extraction of financial entities. No LLM."""
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class FinancialEntity:
    text: str
    entity_type: str
    value: Optional[float]
    unit: str
    confidence: float
    source: str = "NER_PIPELINE"

MULT = {"billion": 1e9, "million": 1e6, "B": 1e9, "M": 1e6}

PATTERNS = {
    "REVENUE": [
        re.compile(r'revenue[s]?\s+(?:of\s+|was\s+)?\$?([\d,]+\.?\d*)\s*(billion|million|B|M)\b', re.I),
        re.compile(r'net\s+sales\s+(?:of\s+)?\$?([\d,]+\.?\d*)\s*(billion|million|B|M)\b', re.I),
    ],
    "GROSS_MARGIN": [re.compile(r'gross\s+margin[s]?\s+(?:of\s+|was\s+|at\s+)?([\d.]+)\s*%', re.I)],
    "EPS": [re.compile(r'(?:diluted\s+)?(?:EPS|earnings\s+per\s+share)\s+(?:of\s+)?\$?([\d.]+)', re.I)],
    "REVENUE_GROWTH": [re.compile(r'revenue\s+(?:grew?|increased?|rose?|up)\s+([\d.]+)\s*%', re.I)],
    "OPERATING_MARGIN": [re.compile(r'operating\s+margin[s]?\s+(?:of\s+|at\s+)?([\d.]+)\s*%', re.I)],
    "NET_INCOME": [re.compile(r'net\s+(?:income|earnings)\s+(?:of\s+)?\$?([\d,]+\.?\d*)\s*(billion|million|B|M)\b', re.I)],
    "FREE_CASH_FLOW": [re.compile(r'free\s+cash\s+flow\s+(?:of\s+)?\$?([\d,]+\.?\d*)\s*(billion|million|B|M)\b', re.I)],
}


class FinancialNER:
    def extract(self, text: str, source: str = "text") -> list[FinancialEntity]:
        entities = []
        for etype, patterns in PATTERNS.items():
            for pat in patterns:
                for m in pat.finditer(text):
                    raw = m.group(1).replace(",", "")
                    try:
                        val = float(raw)
                        groups = m.groups()
                        if len(groups) > 1 and groups[1]:
                            val *= MULT.get(groups[1], 1)
                    except (ValueError, TypeError):
                        val = None
                    unit = "%" if etype in ("GROSS_MARGIN", "OPERATING_MARGIN", "REVENUE_GROWTH") else "USD"
                    entities.append(FinancialEntity(
                        text=m.group(0), entity_type=etype,
                        value=val, unit=unit, confidence=0.95, source=source,
                    ))
        return entities
