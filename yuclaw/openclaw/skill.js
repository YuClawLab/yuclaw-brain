/**
 * YUCLAW Financial Intelligence Skill for OpenClaw
 *
 * Install: copy to ~/.openclaw/skills/yuclaw/
 * Or: openclaw skills install yuclaw-financial
 *
 * Commands:
 *   /yuclaw              — full financial briefing
 *   /yuclaw signals      — top buy/sell signals
 *   /yuclaw regime       — market regime
 *   /yuclaw backtest NVDA — backtest any ticker
 *   /yuclaw portfolio    — optimal allocation
 *   /yuclaw risk         — VaR/Kelly/Sharpe
 *   /yuclaw earnings     — upcoming earnings
 *   /yuclaw insider      — SEC insider activity
 */

const { execSync } = require('child_process');
const fetch = require('node-fetch');

const YUCLAW_API = process.env.YUCLAW_API || 'http://localhost:8000';

async function isAPIRunning() {
    try {
        const resp = await fetch(`${YUCLAW_API}/health`, { timeout: 3000 });
        return resp.ok;
    } catch { return false; }
}

function runCLI(command) {
    try {
        return execSync(`yuclaw ${command} 2>/dev/null`, { encoding: 'utf8', timeout: 60000 });
    } catch { return null; }
}

async function fetchAPI(endpoint) {
    try {
        const resp = await fetch(`${YUCLAW_API}${endpoint}`);
        return await resp.json();
    } catch { return null; }
}

const skill = {
    name: 'yuclaw-financial',
    description: 'YUCLAW Financial Intelligence — real backtests, ZKP audit, Nemotron 120B',
    version: '1.1.0',
    author: 'YuClawLab',

    commands: {
        '/yuclaw': async (args, ctx) => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const [regime, signals, risk] = await Promise.all([
                    fetchAPI('/regime'), fetchAPI('/signals'), fetchAPI('/risk')
                ]);
                const top = (signals || []).slice(0, 5)
                    .map(s => `${s.ticker} ${s.signal} ${s.score > 0 ? '+' : ''}${s.score.toFixed(3)}`)
                    .join('\n');
                return `YUCLAW Financial Brief\n\nRegime: ${regime?.regime || 'UNKNOWN'} (${((regime?.confidence||0)*100).toFixed(0)}%)\n\nTop Signals:\n${top}\n\nRisk: VaR95 ${((risk?.var_95||0)*100).toFixed(2)}% | Sharpe ${(risk?.sharpe||0).toFixed(2)}\n\nDashboard: yuclawlab.github.io/yuclaw-brain`;
            }
            return runCLI('start') || 'YUCLAW: pip install yuclaw && yuclaw start';
        },

        '/yuclaw signals': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const signals = await fetchAPI('/signals');
                const top = (signals || []).slice(0, 8)
                    .map(s => `${s.ticker.padEnd(6)} ${s.signal.padEnd(12)} ${s.score > 0 ? '+' : ''}${s.score.toFixed(3)}`)
                    .join('\n');
                return `YUCLAW Signals\n\n${top}`;
            }
            return runCLI('signals') || 'Install: pip install yuclaw';
        },

        '/yuclaw regime': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const regime = await fetchAPI('/regime');
                return `Market Regime: ${regime?.regime} (${((regime?.confidence||0)*100).toFixed(0)}%)\n-> ${regime?.action || ''}`;
            }
            return runCLI('regime') || 'Install: pip install yuclaw';
        },

        '/yuclaw backtest': async (args) => {
            const ticker = args[0]?.toUpperCase() || 'NVDA';
            return runCLI(`backtest ${ticker}`) || 'Install: pip install yuclaw';
        },

        '/yuclaw portfolio': async () => {
            return runCLI('portfolio') || 'Install: pip install yuclaw';
        },

        '/yuclaw risk': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const risk = await fetchAPI('/risk');
                return `Portfolio Risk\nVaR 95%: ${((risk?.var_95||0)*100).toFixed(2)}%\nSharpe: ${(risk?.sharpe||0).toFixed(2)}\nKelly: ${((risk?.kelly||0)*100).toFixed(1)}%`;
            }
            return runCLI('risk') || 'Install: pip install yuclaw';
        },

        '/yuclaw earnings': async () => runCLI('earnings') || 'Install: pip install yuclaw',
        '/yuclaw insider': async () => runCLI('insider') || 'Install: pip install yuclaw',

        '/yuclaw help': async () => {
            return `YUCLAW Financial Intelligence\n\nCommands:\n/yuclaw           full briefing\n/yuclaw signals   buy/sell signals\n/yuclaw regime    market regime\n/yuclaw backtest  backtest any ticker\n/yuclaw portfolio optimal allocation\n/yuclaw risk      VaR/Kelly/Sharpe\n/yuclaw earnings  earnings calendar\n/yuclaw insider   SEC insider activity\n\nInstall: pip install yuclaw\nDashboard: yuclawlab.github.io/yuclaw-brain`;
        }
    }
};

module.exports = skill;
