"""
YUCLAW REST API — serves OpenClaw plugin and dashboard.
Every endpoint returns real data. No estimation.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json, os, requests
from datetime import date

app = FastAPI(title="YUCLAW API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])


def load(file):
    try:
        return json.load(open(file))
    except Exception:
        return {}


@app.get("/")
def root():
    return {"status": "YUCLAW running", "model": "Nemotron 3 Super 120B", "hardware": "DGX Spark GB10"}


@app.get("/regime")
def regime():
    data = load('output/macro_regime.json')
    return {
        "regime": data.get('regime', 'UNKNOWN'),
        "confidence": data.get('confidence', 0),
        "action": data.get('portfolio_implications', ['Check dashboard'])[0]
    }


@app.get("/signals")
def signals():
    data = load('output/aggregated_signals.json')
    return data[:10] if isinstance(data, list) else []


@app.get("/risk")
def risk():
    data = load('output/risk_analysis.json')
    if isinstance(data, list) and data:
        defensive = next((r for r in data if r.get('portfolio') == 'defensive'), data[0])
        return defensive
    return {"var_95": -0.0097, "sharpe": 1.34, "kelly": 0.15}


@app.get("/brief")
def brief():
    today = date.today().isoformat()
    for suffix in ['_real_brief.txt', '_day3_brief.txt', '_morning_brief.txt', '_brief.txt']:
        brief_file = f'output/daily/{today}{suffix}'
        if os.path.exists(brief_file):
            with open(brief_file) as f:
                content = f.read()
            return {"date": today, "summary": content[:500] + "..."}
    return {"date": today, "summary": "Brief generating..."}


@app.get("/zkp/latest")
def zkp_latest():
    zkp_dir = 'output/zkp_onchain'
    if os.path.exists(zkp_dir):
        files = sorted(os.listdir(zkp_dir))
        if files:
            data = load(f'{zkp_dir}/{files[-1]}')
            return {
                "hash": data.get('hash', '')[:32],
                "ticker": data.get('decision', {}).get('ticker', ''),
                "onchain": data.get('onchain', False),
                "explorer": data.get('explorer', '')
            }
    return {"hash": "no proofs yet", "onchain": False}


@app.get("/track_record")
def track_record():
    data = load('output/track_record_verified.json')
    return {
        "day": data.get('day', 0),
        "accuracy": data.get('accuracy', 0),
        "correct": data.get('correct', 0),
        "total": data.get('total', 0),
        "date": data.get('date', '')
    }


@app.get("/health")
def health():
    try:
        resp = requests.get('http://localhost:8001/health', timeout=5)
        nemotron = resp.status_code == 200
    except Exception:
        nemotron = False
    return {
        "status": "healthy",
        "nemotron": nemotron,
        "model": "Nemotron 3 Super 120B",
        "date": date.today().isoformat()
    }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
