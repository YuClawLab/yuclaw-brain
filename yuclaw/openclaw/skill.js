/**
 * YUCLAW Financial Intelligence Skill for OpenClaw
 *
 * ONE COMMAND INSTALL:
 * bash <(curl -s https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/yuclaw/openclaw/install.sh)
 *
 * Commands:
 *   /yuclaw              — full financial briefing
 *   /yuclaw signals      — top buy/sell signals (167 tickers)
 *   /yuclaw regime       — CRISIS/RISK_OFF/RISK_ON
 *   /yuclaw backtest     — real Calmar from actual prices
 *   /yuclaw portfolio    — Kelly-optimal allocation
 *   /yuclaw risk         — VaR/CVaR/Sharpe/Kelly
 *   /yuclaw earnings     — upcoming earnings calendar
 *   /yuclaw insider      — SEC Form 4 insider activity
 *   /yuclaw zkp          — latest ZKP on-chain proof
 *   /yuclaw help         — show all commands
 */

const { execSync } = require('child_process');

const YUCLAW_API = process.env.YUCLAW_API || 'http://localhost:8000';
const DASHBOARD = 'https://yuclawlab.github.io/yuclaw-brain';
const GITHUB = 'https://github.com/YuClawLab';

async function isAPIRunning() {
    try {
        const resp = await fetch(`${YUCLAW_API}/health`, { signal: AbortSignal.timeout(3000) });
        return resp.ok;
    } catch { return false; }
}

async function fetchAPI(endpoint) {
    try {
        const resp = await fetch(`${YUCLAW_API}${endpoint}`);
        return await resp.json();
    } catch { return null; }
}

function runCLI(command) {
    try {
        return execSync(`yuclaw ${command} 2>/dev/null`, { encoding: 'utf8', timeout: 60000 });
    } catch { return null; }
}

function formatSignals(signals, limit = 8) {
    return signals.slice(0, limit)
        .map(s => `${s.ticker.padEnd(6)} ${s.signal.padEnd(12)} ${s.score > 0 ? '+' : ''}${s.score.toFixed(3)} $${(s.price||0).toFixed(2)}`)
        .join('\n');
}

const skill = {
    name: 'yuclaw-financial',
    description: 'YUCLAW Financial Intelligence — real backtests, ZKP audit trail, Nemotron 120B analysis',
    version: '1.1.0',
    author: 'YuClawLab',
    license: 'MIT',
    homepage: GITHUB,

    commands: {
        '/yuclaw': async (args, ctx) => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const [regime, signals, risk, brief] = await Promise.all([
                    fetchAPI('/regime'), fetchAPI('/signals'), fetchAPI('/risk'), fetchAPI('/brief')
                ]);
                const top = signals ? formatSignals(signals, 5) : 'No signals';
                return `YUCLAW Financial Brief\n\nRegime: ${regime?.regime || 'UNKNOWN'} (${((regime?.confidence||0)*100).toFixed(0)}%)\n-> ${(regime?.action || 'Check dashboard')}\n\nTop Signals:\n${top}\n\nRisk: VaR95 ${((risk?.var_95||0)*100).toFixed(2)}% | Sharpe ${(risk?.sharpe||0).toFixed(2)}\n\nBrief: ${brief?.summary?.slice(0, 150) || 'Generating...'}...\n\nDashboard: ${DASHBOARD}\nInstall: pip install yuclaw`;
            }
            return runCLI('start') || `YUCLAW not running locally.\nInstall: pip install yuclaw\nDashboard: ${DASHBOARD}`;
        },

        '/yuclaw signals': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const signals = await fetchAPI('/signals');
                if (!signals || signals.length === 0) return 'No signals yet. Run: yuclaw start';
                const buys = signals.filter(s => s.signal.includes('BUY')).length;
                const sells = signals.filter(s => s.signal.includes('SELL')).length;
                return `YUCLAW Signals\n\n${formatSignals(signals, 10)}\n\nTotal: ${signals.length} | BUY: ${buys} | SELL: ${sells}`;
            }
            return runCLI('signals') || `Install: pip install yuclaw`;
        },

        '/yuclaw regime': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const regime = await fetchAPI('/regime');
                const implications = (regime?.portfolio_implications || []).map(i => `-> ${i}`).join('\n');
                return `Market Regime: ${regime?.regime} (${((regime?.confidence||0)*100).toFixed(0)}%)\n\n${implications}`;
            }
            return runCLI('regime') || 'Install: pip install yuclaw';
        },

        '/yuclaw backtest': async (args) => {
            const ticker = (args[0] || 'NVDA').toUpperCase();
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const result = await fetchAPI(`/backtest/${ticker}`);
                if (result && result.best_calmar) {
                    return `YUCLAW Backtest — ${ticker}\n\nBest Strategy: ${result.best_strategy}\nCalmar: ${result.best_calmar.toFixed(3)}\nAnnual Return: ${(result.best_annual_return * 100).toFixed(1)}%\nSharpe: ${result.best_sharpe.toFixed(2)}\nYears: ${result.years}\n\nReal math. Not LLM estimation.`;
                }
            }
            return runCLI('backtest') || 'Install: pip install yuclaw';
        },

        '/yuclaw portfolio': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const portfolio = await fetchAPI('/portfolio');
                if (portfolio && portfolio.allocations) {
                    const allocs = Object.entries(portfolio.allocations)
                        .map(([t, p]) => `${t.padEnd(6)} ${(p*100).toFixed(1)}%`)
                        .join('\n');
                    return `YUCLAW Portfolio Optimization\nMethod: ${portfolio.method}\n\n${allocs}\n\n${portfolio.note}`;
                }
            }
            return runCLI('portfolio') || 'Install: pip install yuclaw';
        },

        '/yuclaw risk': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const risk = await fetchAPI('/risk');
                return `Portfolio Risk\n\nVaR 95%:  ${((risk?.var_95||0)*100).toFixed(2)}%\nSharpe:   ${(risk?.sharpe||0).toFixed(2)}\nKelly:    ${((risk?.kelly||0)*100).toFixed(1)}%\n\nReal historical simulation.`;
            }
            return runCLI('risk') || 'Install: pip install yuclaw';
        },

        '/yuclaw earnings': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const earnings = await fetchAPI('/earnings');
                if (earnings && earnings.length > 0) {
                    const list = earnings.slice(0, 8)
                        .map(e => `${e.ticker.padEnd(6)} ${e.earnings_date} (${e.days_until}d)`)
                        .join('\n');
                    return `Upcoming Earnings\n\n${list}`;
                }
                return 'No upcoming earnings in next 30 days';
            }
            return runCLI('earnings') || 'Install: pip install yuclaw';
        },

        '/yuclaw insider': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const insider = await fetchAPI('/insider');
                if (insider && insider.length > 0) {
                    const list = insider.slice(0, 5)
                        .map(t => `${t.ticker.padEnd(6)} ${t.filed} ${(t.entity||'').slice(0,30)}`)
                        .join('\n');
                    return `Insider Activity (SEC Form 4)\n\n${list}\n\nTotal: ${insider.length} filings`;
                }
                return 'No recent insider activity found';
            }
            return runCLI('insider') || 'Install: pip install yuclaw';
        },

        '/yuclaw zkp': async () => {
            const apiRunning = await isAPIRunning();
            if (apiRunning) {
                const zkp = await fetchAPI('/zkp/latest');
                if (zkp && zkp.onchain) {
                    return `YUCLAW ZKP Proof\n\nTicker: ${zkp.ticker}\nHash: ${zkp.hash}\nOn-chain: Ethereum Sepolia\nExplorer: ${zkp.explorer}\n\nEvery signal cryptographically verified.`;
                }
            }
            return `ZKP Vault — Ethereum Sepolia\nDashboard: ${DASHBOARD}`;
        },

        '/yuclaw help': async () => {
            return `YUCLAW Financial Intelligence for OpenClaw\n\nCommands:\n/yuclaw           full briefing\n/yuclaw signals   buy/sell signals (167 tickers)\n/yuclaw regime    CRISIS/RISK_OFF/RISK_ON\n/yuclaw backtest  real Calmar from actual prices\n/yuclaw portfolio Kelly-optimal allocation\n/yuclaw risk      VaR/CVaR/Sharpe/Kelly\n/yuclaw earnings  earnings calendar\n/yuclaw insider   SEC Form 4\n/yuclaw zkp       on-chain ZKP proof\n\nInstall: pip install yuclaw\nDashboard: ${DASHBOARD}\nGitHub: ${GITHUB}`;
        }
    }
};

module.exports = skill;
