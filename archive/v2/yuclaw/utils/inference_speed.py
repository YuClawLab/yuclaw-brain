"""
Measure Ollama inference tokens/sec for the dashboard's stat card.

Hits /api/generate with a short prompt + small num_predict, then reads the
authoritative eval_count and eval_duration fields from the Ollama response
(nanoseconds). Returns a dict suitable for serialization to JSON.

Called once per nightly cron firing — cheap (~5-10s) on top of the nightly
score regeneration. Output cached in output/inference_stats.json; the
dashboard renders the cached value with the timestamp it was measured.
"""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone


OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
DEFAULT_MODEL = 'nemotron-3-super-local:latest'
DEFAULT_N_TOKENS = 50
DEFAULT_TIMEOUT = 120


def measure_inference_stats(model: str = DEFAULT_MODEL,
                            n_tokens: int = DEFAULT_N_TOKENS,
                            timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Run a short generation against Ollama, return measured tokens/sec.

    Uses Ollama's eval_duration (nanoseconds the model spent generating)
    and eval_count (tokens generated) — these are the model's own
    measurement, more accurate than wall-clock around the request.

    On failure returns a dict with tok_per_sec=None and an 'error' field.
    """
    body = json.dumps({
        'model': model,
        'prompt': 'Count: one two three four five.',
        'stream': False,
        'options': {
            'num_predict': n_tokens,
            'temperature': 0.0,
        },
    }).encode()

    req = urllib.request.Request(
        f'{OLLAMA_HOST}/api/generate',
        data=body,
        headers={'Content-Type': 'application/json'},
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read())
    except urllib.error.URLError as e:
        return {
            'tok_per_sec':  None,
            'measured_at':  datetime.now(timezone.utc).isoformat(),
            'model':        model,
            'error':        f'URLError: {e}',
        }
    wall_seconds = time.time() - t0

    eval_count = int(d.get('eval_count') or 0)
    eval_duration_ns = int(d.get('eval_duration') or 0)

    if eval_count <= 0 or eval_duration_ns <= 0:
        return {
            'tok_per_sec':  None,
            'measured_at':  datetime.now(timezone.utc).isoformat(),
            'model':        model,
            'error':        'Ollama returned eval_count or eval_duration of 0',
        }

    tok_per_sec = eval_count / (eval_duration_ns / 1e9)

    return {
        'tok_per_sec':       round(tok_per_sec, 1),
        'measured_at':       datetime.now(timezone.utc).isoformat(),
        'model':             model,
        'eval_count':        eval_count,
        'eval_duration_ms':  round(eval_duration_ns / 1e6, 1),
        'wall_seconds':      round(wall_seconds, 2),
    }


def save_inference_stats(stats: dict, signal_cycle_seconds: float = None,
                          path: str = 'output/inference_stats.json') -> None:
    """
    Persist measurement to disk. Optionally merge in signal_cycle_seconds
    (the nightly pipeline runtime) so the dashboard can show both stats
    sourced from the same file.
    """
    out = dict(stats)
    if signal_cycle_seconds is not None:
        out['signal_cycle_seconds'] = round(signal_cycle_seconds, 1)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)


if __name__ == '__main__':
    # CLI usage: optional arg = signal_cycle_seconds passed by the nightly cron wrapper.
    import sys
    cycle = None
    if len(sys.argv) > 1:
        try:
            cycle = float(sys.argv[1])
        except ValueError:
            pass

    stats = measure_inference_stats()
    save_inference_stats(stats, signal_cycle_seconds=cycle)
    if stats.get('tok_per_sec') is not None:
        print(f"tok/s: {stats['tok_per_sec']}  (eval_count={stats['eval_count']}, "
              f"eval_duration={stats['eval_duration_ms']}ms, wall={stats['wall_seconds']}s)")
    else:
        print(f"inference_speed measurement FAILED: {stats.get('error')}")
    if cycle is not None:
        print(f"signal_cycle_seconds: {cycle}")
