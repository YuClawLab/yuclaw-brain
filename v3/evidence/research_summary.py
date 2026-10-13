"""Descriptive units and composite reconstruction; never estimates reliability."""
from collections import Counter
from datetime import timedelta
import math

from v3.evidence.history import _ts


def denominators(objects, end, days=90):
    end = _ts(end)
    start = end - timedelta(days=days)
    rows = [o for o in objects if start < _ts(o['available_as_of']) <= end]
    counts = Counter(o.get('evidence_type') or 'UNKNOWN' for o in rows)
    accessions = {o['accession_number'] for o in rows if o.get('accession_number')}
    return {'window_start_exclusive': start.isoformat(), 'window_end_inclusive': end.isoformat(),
            'event_objects': len(rows), 'distinct_accessions': len(accessions),
            'objects_without_accession': sum(not o.get('accession_number') for o in rows),
            'by_event_type': dict(sorted(counts.items())),
            'largest_type_share': max(counts.values()) / len(rows) if rows else None,
            'independent_information_count': None,
            'note': 'Multiple events can come from one filing. Counts describe this corpus; neither events nor filings are independent observations by assumption.'}


def composite_anatomy(components, total, weights):
    """Reconcile stored scores/confidences. Legacy weights are explicitly unproven."""
    out = []
    missing = []
    recorded = True
    for cid, current_weight in sorted(weights.items()):
        c = (components or {}).get(cid, {})
        recorded &= 'nominal_weight' in c
        w = c.get('nominal_weight', current_weight)
        score, confidence = c.get('score'), c.get('confidence')
        valid = all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                    for x in (w, score, confidence))
        valid = valid and w >= 0 and 0 <= confidence <= 1
        if not valid:
            missing.append(cid)
        mass = w * confidence if valid and not c.get('not_implemented') else 0.0
        out.append({'id': cid, 'score': score, 'confidence': confidence,
                    'nominal_weight': w, 'weight_source': 'RECORDED' if 'nominal_weight' in c else 'CURRENT_CONFIG',
                    'active': not c.get('not_implemented', False), 'weight_times_confidence': mass,
                    'effective_weight': None, 'contribution': None,
                    'input_status': 'FROZEN_2026-05-18' if cid == 'c4' else ('NOT_IMPLEMENTED' if c.get('not_implemented') else 'NOT_ASSESSED')})
    denominator = sum(x['weight_times_confidence'] for x in out)
    reconstructed = None
    if not missing and denominator > 0:
        for row in out:
            row['effective_weight'] = row['weight_times_confidence'] / denominator
            row['contribution'] = row['effective_weight'] * row['score']
        reconstructed = sum(x['contribution'] for x in out)
    matches = reconstructed is not None and abs(round(reconstructed, 4) - float(total)) <= 0.00005
    return {'formula': 'sum(weight * confidence * score) / sum(weight * confidence), excluding not_implemented components',
            'status': 'INCOMPLETE' if missing or denominator == 0 else ('RECONCILED' if matches else 'MISMATCH'),
            'weight_provenance': 'RECORDED' if recorded else 'CURRENT_CONFIG_RECONCILIATION_ONLY',
            'denominator': denominator if not missing else None, 'reconstructed_score': reconstructed,
            'stored_score': total, 'missing_components': missing, 'components': out,
            'note': 'Confidence is a model input, not a calibrated probability. Current configuration weights do not establish historical weights. C4 is disclosed as frozen; no past score is changed.'}
