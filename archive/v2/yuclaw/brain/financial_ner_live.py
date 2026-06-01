"""
Financial NER — extracts entities from news and SEC filings.
Wired into signal pipeline for fundamental confirmation.
"""
import re, json, os
from datetime import date


FINANCIAL_ENTITIES = {
    'REVENUE_GROWTH': r'revenue.{0,20}(grew|increased|up|rose).{0,20}(\d+\.?\d*)\s*%',
    'EARNINGS_BEAT': r'(beat|exceeded|surpassed).{0,20}(earnings|EPS|estimates)',
    'GUIDANCE_RAISE': r'(raised|increased|improved).{0,20}(guidance|outlook|forecast)',
    'INSIDER_BUY': r'(insider|executive|CEO|CFO).{0,20}(bought|purchased|acquired)',
    'FDA_APPROVAL': r'FDA.{0,20}(approved|granted|cleared)',
    'CONTRACT_WIN': r'(awarded|won|secured).{0,20}(contract|deal|agreement)',
}


def extract_entities(text: str, ticker: str) -> dict:
    entities = {'ticker': ticker, 'date': date.today().isoformat(), 'found': []}

    for entity_type, pattern in FINANCIAL_ENTITIES.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            entities['found'].append({
                'type': entity_type,
                'matches': len(matches),
                'bullish': entity_type in [
                    'REVENUE_GROWTH', 'EARNINGS_BEAT', 'GUIDANCE_RAISE',
                    'INSIDER_BUY', 'FDA_APPROVAL', 'CONTRACT_WIN'
                ]
            })

    bullish = sum(1 for e in entities['found'] if e['bullish'])
    entities['bullish_signals'] = bullish
    entities['score_adjustment'] = bullish * 0.05

    return entities


def run_ner_pipeline():
    print("=== Financial NER Pipeline ===")

    sample_texts = {
        'LUNR': "Intuitive Machines revenue grew 150% as NASA contracts secured and awarded new lunar mission contract",
        'ASTS': "AST SpaceMobile partnerships increased with major telecom providers, insider CEO purchased shares",
        'MRNA': "Moderna raised guidance after FDA approved new variant vaccine, earnings beat estimates by 15%",
    }

    os.makedirs('output/ner', exist_ok=True)
    for ticker, text in sample_texts.items():
        entities = extract_entities(text, ticker)
        print(f"{ticker}: {entities['bullish_signals']} bullish signals, score adj: +{entities['score_adjustment']:.2f}")
        with open(f"output/ner/{ticker}_{date.today()}.json", 'w') as f:
            json.dump(entities, f, indent=2)


if __name__ == '__main__':
    run_ner_pipeline()
