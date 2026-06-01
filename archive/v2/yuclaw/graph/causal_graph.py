"""
YUCLAW Causal Knowledge Graph — maps second and third-order effects.

When news breaks about TSMC, this graph tells you:
  TSMC disruption → NVIDIA chip delay → DELL server margins collapse
  TSMC disruption → AMD supply squeeze → INTC gains share

Standard AI sees ticker in isolation. This sees the chain reaction.
"""
import json, os
import networkx as nx
from datetime import datetime

class CausalGraph:

    def __init__(self):
        self.G = nx.DiGraph()
        self._build_base_graph()

    def _build_base_graph(self):
        """Build the global supply chain / dependency graph."""

        # Semiconductor chain
        self._add_chain('TSMC', 'supplies_chips_to', ['NVDA', 'AMD', 'AAPL', 'QCOM', 'AVGO'])
        self._add_chain('NVDA', 'supplies_gpus_to', ['DELL', 'HPE', 'MSFT', 'GOOG', 'META', 'AMZN'])
        self._add_chain('AMD', 'supplies_cpus_to', ['DELL', 'HPE', 'MSFT', 'GOOG'])
        self._add_chain('ASML', 'supplies_lithography_to', ['TSMC', 'INTC', 'Samsung'])
        self._add_chain('AMAT', 'supplies_equipment_to', ['TSMC', 'INTC', 'Samsung', 'KLAC'])
        self._add_chain('KLAC', 'inspects_chips_for', ['TSMC', 'INTC', 'Samsung'])
        self._add_chain('MRVL', 'supplies_networking_to', ['AMZN', 'MSFT', 'GOOG'])
        self._add_chain('AVGO', 'supplies_networking_to', ['AAPL', 'MSFT', 'GOOG'])

        # Cloud / AI chain
        self._add_chain('MSFT', 'cloud_competes_with', ['AMZN', 'GOOG'])
        self._add_chain('MSFT', 'ai_partner_of', ['OpenAI'])
        self._add_chain('GOOG', 'ai_competes_with', ['MSFT', 'META'])

        # Energy chain
        self._add_chain('WTI', 'price_impacts', ['XOM', 'CVX', 'COP', 'OXY', 'SLB'])
        self._add_chain('WTI', 'cost_impacts', ['DAL', 'UAL', 'LUV', 'AAL'])
        self._add_chain('OPEC', 'controls_supply_of', ['WTI', 'BRENT'])
        self._add_chain('EIA_INVENTORY', 'signals_demand_for', ['WTI', 'BRENT'])

        # AI data center energy
        self._add_chain('AI_DEMAND', 'increases_power_for', ['VST', 'CEG', 'NRG', 'SO'])
        self._add_chain('NVDA', 'drives_power_demand_via', ['AI_DEMAND'])

        # Space / satellite
        self._add_chain('ASTS', 'competes_with', ['LUNR', 'RKLB'])
        self._add_chain('SpaceX', 'launches_for', ['ASTS', 'LUNR'])

        # Biotech / pharma
        self._add_chain('FDA', 'approves_drugs_for', ['MRNA', 'PFE', 'LLY', 'ABBV'])
        self._add_chain('MRNA', 'competes_with', ['PFE', 'BNTX'])

        # Macro
        self._add_chain('FED_RATE', 'impacts', ['TLT', 'IEF', 'HYG', 'SPY', 'QQQ'])
        self._add_chain('FED_RATE', 'strengthens', ['DXY'])
        self._add_chain('DXY', 'hurts_earnings_of', ['AAPL', 'MSFT', 'GOOG', 'META'])
        self._add_chain('CHINA_GDP', 'demand_for', ['CAT', 'DE', 'FCX', 'AA'])

        # Geopolitical
        self._add_chain('TAIWAN_RISK', 'disrupts', ['TSMC'])
        self._add_chain('MIDDLE_EAST', 'disrupts', ['WTI', 'BRENT'])
        self._add_chain('TARIFF', 'hurts', ['AAPL', 'TSLA', 'NKE'])

        # Consumer
        self._add_chain('CONSUMER_SPEND', 'benefits', ['AMZN', 'WMT', 'COST', 'TGT'])
        self._add_chain('HOUSING', 'benefits', ['HD', 'LOW', 'DHI', 'LEN'])

        print(f"Graph built: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")

    def _add_chain(self, source: str, relationship: str, targets: list):
        for target in targets:
            self.G.add_edge(source, target, relationship=relationship)

    def get_impact_chain(self, event_node: str, max_depth: int = 3) -> dict:
        """Given a disruption at event_node, trace ALL downstream effects."""

        if event_node not in self.G:
            # Try to find partial match
            matches = [n for n in self.G.nodes if event_node.upper() in n.upper()]
            if matches:
                event_node = matches[0]
            else:
                return {'error': f'{event_node} not in graph', 'available': list(self.G.nodes)[:20]}

        impacts = {}
        visited = set()

        def trace(node, depth, path):
            if depth > max_depth or node in visited:
                return
            visited.add(node)

            for successor in self.G.successors(node):
                edge = self.G[node][successor]
                rel = edge.get('relationship', 'impacts')

                impact = {
                    'ticker': successor,
                    'relationship': rel,
                    'depth': depth,
                    'path': path + [f"{node} --[{rel}]--> {successor}"],
                    'order': f"{'1st' if depth==1 else '2nd' if depth==2 else '3rd'}",
                }

                if successor not in impacts or impacts[successor]['depth'] > depth:
                    impacts[successor] = impact

                trace(successor, depth + 1, impact['path'])

        trace(event_node, 1, [])

        # Sort by depth then alphabetical
        sorted_impacts = sorted(impacts.values(), key=lambda x: (x['depth'], x['ticker']))

        result = {
            'event': event_node,
            'timestamp': datetime.utcnow().isoformat(),
            'total_affected': len(sorted_impacts),
            'by_order': {
                '1st_order': [i for i in sorted_impacts if i['depth'] == 1],
                '2nd_order': [i for i in sorted_impacts if i['depth'] == 2],
                '3rd_order': [i for i in sorted_impacts if i['depth'] >= 3],
            },
            'all_impacts': sorted_impacts
        }

        return result

    def explain_chain(self, event_node: str) -> str:
        """Human-readable explanation of impact chain."""

        result = self.get_impact_chain(event_node)
        if 'error' in result:
            return f"Node '{event_node}' not found. Try: TSMC, NVDA, WTI, FED_RATE, TAIWAN_RISK"

        output = f"\n{'='*60}"
        output += f"\n CAUSAL CHAIN: {event_node} disruption"
        output += f"\n{'='*60}"
        output += f"\n Total affected: {result['total_affected']} entities\n"

        for order_name, impacts in result['by_order'].items():
            if impacts:
                output += f"\n {order_name.upper()} EFFECTS:"
                for imp in impacts:
                    chain = ' -> '.join(imp['path'])
                    output += f"\n   {imp['ticker']:8} via {chain}"

        return output

    def get_second_order_trades(self, event_node: str) -> list:
        """Return actionable 2nd/3rd order trades that the market hasn't priced in."""

        result = self.get_impact_chain(event_node)
        if 'error' in result:
            return []

        trades = []
        for imp in result['all_impacts']:
            if imp['depth'] >= 2:  # Only 2nd order and beyond
                trades.append({
                    'ticker': imp['ticker'],
                    'order': imp['order'],
                    'chain': ' -> '.join(imp['path']),
                    'edge': 'Second-order effects are slower to price in'
                })

        return trades

    def save(self):
        os.makedirs('output/graph', exist_ok=True)

        data = {
            'nodes': list(self.G.nodes),
            'edges': [
                {
                    'source': u,
                    'target': v,
                    'relationship': d.get('relationship', '')
                }
                for u, v, d in self.G.edges(data=True)
            ],
            'stats': {
                'total_nodes': self.G.number_of_nodes(),
                'total_edges': self.G.number_of_edges(),
                'built': datetime.utcnow().isoformat()
            }
        }

        with open('output/graph/causal_graph.json', 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Graph saved: {data['stats']['total_nodes']} nodes, {data['stats']['total_edges']} edges")


if __name__ == '__main__':
    graph = CausalGraph()
    graph.save()

    # Demo scenarios
    scenarios = ['TSMC', 'WTI', 'FED_RATE', 'TAIWAN_RISK', 'NVDA']
    for s in scenarios:
        print(graph.explain_chain(s))
        trades = graph.get_second_order_trades(s)
        if trades:
            print(f"\n  Second-order trade ideas:")
            for t in trades[:3]:
                print(f"    {t['ticker']:6} ({t['order']}) -- {t['chain']}")
