/**
 * YUCLAW Financial Intelligence Plugin for OpenClaw
 * Real backtests. ZKP audit. Nemotron 120B local.
 */

const fetch = require('node-fetch');
const YUCLAW_API = process.env.YUCLAW_API || 'http://localhost:8000';

const commands = {
  '/yuclaw regime': async () => {
    const r = await fetch(`${YUCLAW_API}/regime`).then(r => r.json());
    return `YUCLAW Regime: ${r.regime} (${(r.confidence*100).toFixed(0)}%)\n-> ${r.action}`;
  },
  '/yuclaw signals': async () => {
    const s = await fetch(`${YUCLAW_API}/signals`).then(r => r.json());
    const top = s.slice(0,5).map(x => `${x.ticker} ${x.signal} ${x.score > 0 ? '+' : ''}${x.score.toFixed(3)}`).join('\n');
    return `YUCLAW Top Signals:\n${top}`;
  },
  '/yuclaw brief': async () => {
    const b = await fetch(`${YUCLAW_API}/brief`).then(r => r.json());
    return `YUCLAW Brief:\n${b.summary}`;
  },
  '/yuclaw risk': async () => {
    const r = await fetch(`${YUCLAW_API}/risk`).then(r => r.json());
    return `YUCLAW Risk:\nVaR95: ${(r.var_95*100).toFixed(2)}%\nSharpe: ${r.sharpe.toFixed(2)}\nKelly: ${(r.kelly*100).toFixed(1)}%`;
  },
  '/yuclaw zkp': async () => {
    const z = await fetch(`${YUCLAW_API}/zkp/latest`).then(r => r.json());
    return `YUCLAW ZKP:\nLatest proof: ${z.hash}\nOn-chain: ${z.explorer}`;
  }
};

module.exports = { commands };
