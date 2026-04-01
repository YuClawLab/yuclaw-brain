"""
YUCLAW ATROS Daemon — persistent monitoring agent.
Heartbeat every 60s, AutoDream after 4PM ET daily.
Atomic writes, last_dream_date flag.
"""
import time
import json
import os
import requests
from datetime import datetime, date

MODEL = os.environ.get('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
ENDPOINT = os.environ.get('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')
HEARTBEAT_INTERVAL = 60
ALERT_FILE = 'output/daemon/alerts.json'
STATE_FILE = 'output/daemon/state.json'
MEMORY_FILE = 'output/daemon/memory.json'


def load(f):
    try:
        with open(f, 'r') as fp:
            return json.load(fp)
    except Exception:
        return None


def save(f, data):
    os.makedirs(os.path.dirname(f), exist_ok=True)
    temp_file = f + '.tmp'
    with open(temp_file, 'w') as fp:
        json.dump(data, fp, indent=2)
    os.replace(temp_file, f)


class YUCLAWDaemon:
    def __init__(self):
        os.makedirs('output/daemon', exist_ok=True)
        self.state = load(STATE_FILE) or {
            'last_regime': None,
            'last_signals': {},
            'last_oil_price': 0,
            'last_track_day': 0,
            'last_dream_date': None,
            'alerts_sent': 0,
            'started': datetime.now().isoformat()
        }
        self.memory = load(MEMORY_FILE) or {'daily_summaries': []}
        print(f"ATROS Daemon initialized — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    def heartbeat(self) -> list:
        alerts = []
        now = datetime.now()

        # Regime change detection
        regime = load('output/macro_regime.json')
        if regime:
            current_regime = regime.get('regime')
            if current_regime != self.state.get('last_regime') and self.state.get('last_regime'):
                alert = {
                    'type': 'REGIME_CHANGE', 'severity': 'HIGH',
                    'message': f"Regime changed: {self.state['last_regime']} -> {current_regime}",
                    'timestamp': now.isoformat()
                }
                alerts.append(alert)
                print(f"HIGH ALERT: {alert['message']}")
            self.state['last_regime'] = current_regime

        # Signal change detection
        signals = load('output/aggregated_signals.json')
        if isinstance(signals, list):
            for s in signals[:10]:
                ticker = s['ticker']
                score = s.get('score', 0)
                last_score = self.state['last_signals'].get(ticker, 0)
                if abs(score - last_score) > 0.4:
                    direction = 'strengthened' if abs(score) > abs(last_score) else 'weakened'
                    alerts.append({
                        'type': 'SIGNAL_CHANGE', 'severity': 'MEDIUM',
                        'message': f"{ticker} signal {direction}: {last_score:+.3f} -> {score:+.3f}",
                        'timestamp': now.isoformat()
                    })
                self.state['last_signals'][ticker] = score

        # Track record update
        track = load('output/track_record_verified.json')
        if track:
            day = track.get('day', 0)
            if day > self.state.get('last_track_day', 0):
                alerts.append({
                    'type': 'TRACK_UPDATE', 'severity': 'LOW',
                    'message': f"Track record Day {day}: {track.get('accuracy', 0):.0%} accuracy",
                    'timestamp': now.isoformat()
                })
                self.state['last_track_day'] = day

        save(STATE_FILE, self.state)

        if alerts:
            existing = load(ALERT_FILE) or []
            existing.extend(alerts)
            save(ALERT_FILE, existing[-100:])
            self.state['alerts_sent'] += len(alerts)

        return alerts

    def auto_dream(self):
        today_str = str(date.today())
        print(f"\n=== ATROS AutoDream — {today_str} ===")
        try:
            signals = load('output/aggregated_signals.json') or []
            alerts = load(ALERT_FILE) or []
            track = load('output/track_record_verified.json') or {}
            today_alerts = [a for a in alerts if a.get('timestamp', '').startswith(today_str)]
            summary = {
                'date': today_str,
                'total_signals': len(signals) if isinstance(signals, list) else 0,
                'alerts_today': len(today_alerts),
                'track_day': track.get('day', 0),
                'track_accuracy': track.get('accuracy', 0),
                'regime': self.state.get('last_regime', 'UNKNOWN')
            }
            try:
                resp = requests.post(
                    f'{ENDPOINT}/chat/completions',
                    json={
                        'model': MODEL,
                        'messages': [
                            {'role': 'system', 'content': 'Synthesize today into 2 dense sentences. Identify dominant market narrative. Discard noise.'},
                            {'role': 'user', 'content': f"Today: {json.dumps(summary)}"}
                        ],
                        'max_tokens': 150
                    },
                    timeout=60
                )
                msg = resp.json()['choices'][0]['message']
                summary['nemotron_synthesis'] = msg.get('content') or msg.get('reasoning_content') or ''
            except Exception:
                summary['nemotron_synthesis'] = f"Day {summary['track_day']}: {summary['regime']} regime. {len(today_alerts)} alerts."

            self.memory['daily_summaries'].append(summary)
            self.memory['daily_summaries'] = self.memory['daily_summaries'][-30:]
            save(MEMORY_FILE, self.memory)
            self.state['last_dream_date'] = today_str
            save(STATE_FILE, self.state)
            print(f"AutoDream: {summary['nemotron_synthesis'][:100]}...")
        except Exception as e:
            print(f"AutoDream error: {e}")

    def run(self):
        print("YUCLAW ATROS Daemon running...")
        while True:
            try:
                self.heartbeat()
                today_str = str(date.today())
                now = datetime.now()
                if now.hour >= 16 and self.state.get('last_dream_date') != today_str:
                    self.auto_dream()
                time.sleep(HEARTBEAT_INTERVAL)
            except KeyboardInterrupt:
                print("ATROS Daemon stopped")
                break
            except Exception as e:
                print(f"Heartbeat error: {e}")
                time.sleep(30)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    daemon = YUCLAWDaemon()
    daemon.run()
