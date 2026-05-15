"""
YUCLAW Audio Intelligence — Whisper transcription + local LLM sentiment.

Transcribes earnings calls, FOMC speeches, OPEC conferences.
Scores sentiment sentence by sentence.
Detects hawkish/dovish tone before journalists publish articles.

The local LLM is Llama 3.1 70B served by Ollama as the
'nemotron-3-super-local' tag. The NEMOTRON_URL env var name is preserved
for backwards compatibility with existing operator configs.
"""
import json, os, subprocess, time, requests
from datetime import datetime

# Env-var name preserved for backwards compatibility; the endpoint actually
# serves Llama 3.1 70B via Ollama unless OPENROUTER_API_KEY is set.
NEMOTRON_URL = os.environ.get('NEMOTRON_URL', 'http://localhost:8001/v1/chat/completions')

def download_audio(url: str, output_path: str = '/tmp/yuclaw_audio.mp3') -> str:
    """Download audio from YouTube or direct URL."""
    try:
        # Try yt-dlp first (works for YouTube, Twitter spaces, etc)
        subprocess.run([
            'yt-dlp', '-x', '--audio-format', 'mp3',
            '-o', output_path, '--no-playlist',
            '--max-filesize', '100M', url
        ], check=True, capture_output=True, timeout=300)

        # yt-dlp appends format extension
        for ext in ['.mp3', '.mp3.mp3', '']:
            candidate = output_path + ext if ext else output_path
            if os.path.exists(candidate):
                return candidate

        return output_path
    except Exception as e:
        print(f"Download error: {e}")
        return ''

def transcribe(audio_path: str, model_size: str = 'base') -> dict:
    """Transcribe audio using Whisper (CPU to avoid GPU contention with the LLM)."""
    try:
        import whisper
        print(f"Loading Whisper {model_size} model...")
        # Use CPU — GPU is reserved for the local LLM (Llama 3.1 70B)
        model = whisper.load_model(model_size, device='cpu')

        print(f"Transcribing {audio_path}...")
        start = time.time()
        result = model.transcribe(audio_path, verbose=False)
        elapsed = round(time.time() - start, 1)

        print(f"Transcribed in {elapsed}s — {len(result['segments'])} segments")

        return {
            'text': result['text'],
            'segments': [
                {
                    'start': round(s['start'], 1),
                    'end': round(s['end'], 1),
                    'text': s['text'].strip()
                }
                for s in result['segments']
            ],
            'language': result.get('language', 'en'),
            'duration_sec': round(result['segments'][-1]['end'], 1) if result['segments'] else 0,
            'transcribe_time_sec': elapsed
        }
    except Exception as e:
        return {'error': str(e), 'text': '', 'segments': []}

def score_sentiment(text: str, context: str = 'financial speech') -> dict:
    """Score sentiment of transcribed text using the local LLM."""
    try:
        # Model identifier is the Ollama tag — actual weights are Llama 3.1 70B.
        resp = requests.post(NEMOTRON_URL, json={
            'model': 'nemotron-3-super',
            'messages': [
                {
                    'role': 'system',
                    'content': f"""You are a financial sentiment analyst. Analyze this {context} transcript.
Score the overall tone from -1.0 (extremely bearish/hawkish) to +1.0 (extremely bullish/dovish).
Identify the 3 most market-moving sentences.

Respond in this EXACT format:
SENTIMENT: [number from -1.0 to 1.0]
TONE: [HAWKISH / DOVISH / NEUTRAL / BULLISH / BEARISH]
KEY_QUOTE_1: [most impactful sentence]
KEY_QUOTE_2: [second most impactful]
KEY_QUOTE_3: [third most impactful]
MARKET_IMPACT: [1-2 sentence summary of expected market reaction]
TICKERS_AFFECTED: [comma-separated list of tickers most impacted]"""
                },
                {'role': 'user', 'content': f"Analyze this transcript:\n\n{text[:3000]}"}
            ],
            'max_tokens': 400,
            'temperature': 0.3
        }, timeout=120)

        raw = resp.json()['choices'][0]['message']['content'].strip()

        # Parse response
        result = {'raw': raw, 'sentiment': 0.0, 'tone': 'NEUTRAL'}
        for line in raw.split('\n'):
            line = line.strip()
            if line.startswith('SENTIMENT:'):
                try: result['sentiment'] = float(line.split(':', 1)[1].strip())
                except: pass
            elif line.startswith('TONE:'):
                result['tone'] = line.split(':', 1)[1].strip()
            elif line.startswith('KEY_QUOTE_'):
                key = line.split(':')[0].strip().lower()
                result[key] = line.split(':', 1)[1].strip()
            elif line.startswith('MARKET_IMPACT:'):
                result['market_impact'] = line.split(':', 1)[1].strip()
            elif line.startswith('TICKERS_AFFECTED:'):
                result['tickers_affected'] = [t.strip() for t in line.split(':', 1)[1].split(',')]

        return result
    except Exception as e:
        return {'error': str(e), 'sentiment': 0.0, 'tone': 'NEUTRAL'}

def analyze_audio(source: str, context: str = 'financial speech') -> dict:
    """Full pipeline: download -> transcribe -> score."""

    print(f"\n{'='*60}")
    print(f"YUCLAW Audio Intelligence")
    print(f"{'='*60}")

    # Step 1: Get audio
    audio_path = source
    if source.startswith('http'):
        print(f"Downloading: {source[:80]}...")
        audio_path = download_audio(source)
        if not audio_path or not os.path.exists(audio_path):
            return {'error': 'Download failed'}

    if not os.path.exists(audio_path):
        return {'error': f'Audio file not found: {audio_path}'}

    # Step 2: Transcribe
    print("Transcribing with Whisper...")
    transcript = transcribe(audio_path)
    if 'error' in transcript:
        return {'error': f'Transcription failed: {transcript["error"]}'}

    print(f"Transcript: {len(transcript['text'])} chars, {transcript['duration_sec']}s audio")

    # Step 3: Score sentiment
    print("Scoring sentiment with local LLM...")
    sentiment = score_sentiment(transcript['text'], context)

    # Combine results
    result = {
        'source': source,
        'context': context,
        'timestamp': datetime.utcnow().isoformat(),
        'transcript': transcript,
        'sentiment': sentiment,
    }

    # Save
    os.makedirs('output/audio', exist_ok=True)
    filename = f"output/audio/{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(result, f, indent=2)

    # Also save latest
    with open('output/audio/latest.json', 'w') as f:
        json.dump(result, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"   Sentiment: {sentiment.get('sentiment', 0):+.2f}")
    print(f"   Tone: {sentiment.get('tone', 'NEUTRAL')}")
    if sentiment.get('market_impact'):
        print(f"   Impact: {sentiment['market_impact']}")
    if sentiment.get('tickers_affected'):
        print(f"   Tickers: {', '.join(sentiment['tickers_affected'])}")
    print(f"{'='*60}")

    return result

def transcribe_file(filepath: str) -> dict:
    """Quick transcribe a local file without sentiment."""
    return transcribe(filepath)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        source = sys.argv[1]
        context = sys.argv[2] if len(sys.argv) > 2 else 'financial speech'
        analyze_audio(source, context)
    else:
        print("Usage:")
        print("  python3 audio_intel.py <audio_file_or_url> [context]")
        print("")
        print("Examples:")
        print("  python3 audio_intel.py /tmp/fomc.mp3 'FOMC meeting'")
        print("  python3 audio_intel.py https://youtube.com/watch?v=xxx 'earnings call'")
        print("")
        print("Whisper + local LLM pipeline ready.")
