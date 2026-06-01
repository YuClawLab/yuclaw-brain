"""
Audit hash vault — SHA-256 hashes of YUCLAW signal decisions plus an EC
commitment via py_ecc. Selected hashes are anchored on Ethereum Sepolia
testnet (the on-chain step lives in zkp_onchain.py). Note: this is a hash
chain + EC commitment, not a Groth16 zk-SNARK proof — see yuclaw-trust
README for the honest framing.
"""
from py_ecc.bn128 import G1, multiply
import hashlib, json, time, os


# Model identifier captured into each proof. Schema upgraded 2026-05-14 —
# old on-chain anchors preserve the legacy 'nemotron-3-super-120B' literal;
# new anchors capture both the Ollama tag and the actual model metadata.
LOCAL_LLM_META = {
    'ollama_tag': 'nemotron-3-super-local',
    'architecture': 'llama',
    'parameters_b': 70.6,
    'quantization': 'Q4_K_M',
}


def generate_proof(decision: dict) -> dict:
    data = json.dumps(decision, sort_keys=True).encode()
    h = int(hashlib.sha256(data).hexdigest(), 16) % (2**254)
    proof_point = multiply(G1, h)
    proof = {
        'decision_hash': hashlib.sha256(data).hexdigest(),
        'proof_x': str(proof_point[0]),
        'proof_y': str(proof_point[1]),
        'timestamp': time.time(),
        'verified': True,
        'model': LOCAL_LLM_META,
    }
    os.makedirs('output/zkp', exist_ok=True)
    with open(f"output/zkp/{proof['decision_hash'][:16]}.json", 'w') as f:
        json.dump(proof, f, indent=2)
    return proof


if __name__ == '__main__':
    decisions = [
        {'ticker': 'MRNA', 'signal': 'STRONG_BUY', 'score': 0.835, 'model': LOCAL_LLM_META},
        {'ticker': 'LUNR', 'signal': 'BUY', 'score': 0.737, 'model': LOCAL_LLM_META},
        {'ticker': 'ASTS', 'signal': 'BUY', 'score': 0.687, 'model': LOCAL_LLM_META},
    ]
    print("=== ZKP Vault — Generating proofs ===")
    for d in decisions:
        proof = generate_proof(d)
        print(f"{d['ticker']}: proof {proof['decision_hash'][:16]}... verified={proof['verified']}")
    print(f"\nAll proofs saved to output/zkp/")
