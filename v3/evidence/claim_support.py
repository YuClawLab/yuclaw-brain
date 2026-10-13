"""Conservative checks for earnings comparisons; never a general truth detector."""
from __future__ import annotations

import math
import re
from datetime import datetime

_UP = re.compile(r'\b(?:beat|beats|beating|exceed(?:s|ed|ing)?|above|ahead of|surpass(?:ed|es)?)\b', re.I)
_DOWN = re.compile(r'\b(?:miss(?:ed|es|ing)?|below|short of|underperform(?:ed|s)?)\b', re.I)
_BENCH = re.compile(r'\b(?:expectations?|consensus|estimates?|forecast(?:s)?)\b', re.I)


def assess(event_type: str, excerpt: str, comparison: dict | None = None) -> dict:
    if event_type not in ('EARNINGS_BEAT', 'EARNINGS_MISS'):
        return {'status': 'NOT_ASSESSED', 'reason': 'This check covers earnings expectations comparisons only.'}
    direction = _UP if event_type == 'EARNINGS_BEAT' else _DOWN
    opposite = _DOWN if event_type == 'EARNINGS_BEAT' else _UP
    # Require comparison terms in the same sentence; preserve conservative
    # refusal for ambiguous passages rather than inferring from profitability.
    explicit = any(direction.search(sentence) and _BENCH.search(sentence) and not opposite.search(sentence) and not re.search(r'\b(?:not|never|failed to)\b', sentence, re.I)
                   for sentence in re.split(r'[.!?;]\s+', excerpt or ''))
    if not explicit:
        return {'status': 'UNSUPPORTED_COMPARISON', 'reason': 'The cited passage does not explicitly establish the classified comparison with expectations. Original classification retained as a historical record.'}
    if comparison is None:
        return {'status': 'TEXTUAL_COMPARISON_ONLY', 'reason': 'The passage states a comparison. Actual/benchmark values, units and forecast timing have not been independently verified.'}
    if not isinstance(comparison, dict):
        return {'status': 'INVALID', 'reason': 'Structured comparison must be an object.'}
    required = ('actual', 'expected', 'metric', 'period', 'currency', 'basis', 'actual_span',
                'expected_span', 'benchmark_source', 'benchmark_published_at', 'result_published_at')
    if any(k not in comparison or comparison[k] in (None, '') for k in required):
        return {'status': 'INCOMPLETE', 'reason': 'Structured comparison lacks required value, source, unit, period or timing fields.'}
    a, e = comparison['actual'], comparison['expected']
    if any(isinstance(x, bool) or not isinstance(x, (int,float)) or not math.isfinite(x) for x in (a,e)):
        return {'status': 'INVALID', 'reason': 'Finite actual and expected values required.'}
    try:
        b = datetime.fromisoformat(comparison['benchmark_published_at'].replace('Z','+00:00'))
        r = datetime.fromisoformat(comparison['result_published_at'].replace('Z','+00:00'))
        if b.tzinfo is None or r.tzinfo is None or b >= r:
            raise ValueError('benchmark must predate results, with explicit timezones')
    except (ValueError,TypeError,AttributeError):
        return {'status': 'INVALID', 'reason': 'The benchmark must predate results and both timestamps require timezones.'}
    if (event_type == 'EARNINGS_BEAT' and a <= e) or (event_type == 'EARNINGS_MISS' and a >= e):
        return {'status': 'CONTRADICTED', 'reason': 'Actual and expected values contradict the event direction.'}
    return {'status': 'STRUCTURE_CONSISTENT', 'reason': 'Arithmetic and declared timing agree. Source authenticity, unit compatibility and semantic entailment still require source verification.'}
