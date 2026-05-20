# First signal — under 1 minute

> Research/education only — not investment advice.

```bash
pip install yuclaw-py
```

```python
import yuclaw_py

client = yuclaw_py.Client()   # source='postgres' default; needs the local stack
sig = client.signal("NVDA")

print(f"NVDA: {sig['label']}  score {sig['score']:+.3f}")
# NVDA: NEUTRAL  score +0.312

# The compliance posture is on every signal-bearing return:
print(sig["compliance"])
# {'not_advice': True, 'research_only': True, 'not_registered_adviser': True}
```

To use the hosted REST endpoint instead of running the v3.0 pipeline locally:

```python
client = yuclaw_py.Client(source="api", base_url="https://api.yuclaw.example/v3")
```

Both modes return the exact same dict shape and embed the same compliance payload.
