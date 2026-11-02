"""Financial-data and public-boundary regressions for the research scoreboard."""
import hashlib,json,pathlib,sys,tempfile,unittest
from decimal import Decimal
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from v3.web.scoreboard_research import load_research,source_links
from v3.web.scoreboard_page import load_notes,note_card
from v3.web.render_scoreboard import render

class ResearchBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=pathlib.Path(self.tmp.name);(self.d/'why').mkdir()
        self.cutoff='2026-10-30T23:00:00+00:00'
        self.put('coverage.json',{'schema':'coverage/1','as_of':self.cutoff,'basis':{'window_days':90},'source_identity':{'sha256':'a'*64},'ticker_set':{'count':2},'tickers':{'AMD':{'events_90d':2},'SMH':{'events_90d':0}}})
        self.put('explorer_data.json',{'coverage_source':{'as_of':self.cutoff,'source_sha256':'a'*64},'rows':[{'ticker':'AMD','sector':'Technology'},{'ticker':'SMH','sector':'Sector ETF'}]})
        events=[{'ticker':'AMD','available_as_of':stamp,'filing_date':stamp[:10],'accession_number':acc,'evidence_type':'INSIDER_SELL'} for stamp,acc in [('2026-08-01T23:00:00+00:00','0000002488-26-000001'),('2026-10-30T22:30:00+00:00','0000002488-26-000002'),('2026-10-30T16:30:00-06:00','0000002488-26-000002'),('2026-10-31T00:00:00+00:00','0000002488-26-000003')]]
        for tk,objs in [('AMD',events),('SMH',[])]:
            h={'ticker':tk,'build_id':'test','collection':{'build_id':'test','completeness':'COMPLETE','returned':len(objs),'total_available':len(objs),'corpus_start':'2026-01-01T00:00:00Z','corpus_end':self.cutoff},'evidence_objects':objs}
            self.put('why/'+tk+'.history.json',h)
        self.rebind()
    def tearDown(self):self.tmp.cleanup()
    def put(self,p,d): (self.d/p).write_text(json.dumps(d))
    def rebind(self):
        files={}
        for tk in ['AMD','SMH']:
            p='why/'+tk+'.history.json';raw=(self.d/p).read_bytes();files[tk]={'path':p,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'count':len(json.loads(raw)['evidence_objects'])}
        self.put('why/history_manifest.json',{'schema':'why-history-manifest/1','build_id':'test','files':files})
    def change_history(self,change):
        p='why/AMD.history.json';d=json.loads((self.d/p).read_text());change(d);self.put(p,d);self.rebind()
    def test_cutoff_utc_boundary_and_distinct_filings(self):
        d=load_research(self.d);self.assertEqual(d['status'],'OK');self.assertEqual(d['summary']['events'],2);self.assertEqual(d['summary']['distinct_filings'],1)
        self.assertEqual(d['rows'][0]['filings'][0]['records'],2);self.assertEqual(d['rows'][1]['kind'],'Fund / macro')
    def test_tampered_history_does_not_become_zero(self):
        p=self.d/'why/AMD.history.json';p.write_bytes(p.read_bytes()+b' ')
        d=load_research(self.d);self.assertEqual(d['status'],'PARTIAL');self.assertEqual(d['rows'][0]['status'],'UNAVAILABLE');self.assertNotIn('events_90d',d['rows'][0]);self.assertEqual(d['summary']['without_evidence'],1)
    def test_missing_history_is_unavailable(self):
        (self.d/'why/AMD.history.json').unlink();self.assertEqual(load_research(self.d)['rows'][0]['status'],'UNAVAILABLE')
    def test_capped_history_refused_even_with_valid_hash(self):
        self.change_history(lambda d:d['collection'].update(completeness='PREVIEW'));self.assertEqual(load_research(self.d)['rows'][0]['status'],'UNAVAILABLE')
    def test_insufficient_historical_window_refused(self):
        self.change_history(lambda d:d['collection'].update(corpus_start='2026-09-01T00:00:00Z'));self.assertEqual(load_research(self.d)['rows'][0]['status'],'UNAVAILABLE')
    def test_synthetic_history_refused(self):
        self.change_history(lambda d:d.update(synthetic=True));self.assertEqual(load_research(self.d)['rows'][0]['status'],'UNAVAILABLE')
    def test_build_mismatch_refused(self):
        self.change_history(lambda d:d.update(build_id='other'));self.assertEqual(load_research(self.d)['rows'][0]['status'],'UNAVAILABLE')
    def test_count_mismatch_refused(self):
        d=json.loads((self.d/'coverage.json').read_text());d['tickers']['AMD']['events_90d']=99;self.put('coverage.json',d);self.assertEqual(load_research(self.d)['rows'][0]['status'],'UNAVAILABLE')
    def test_different_coverage_snapshot_refused(self):
        d=json.loads((self.d/'explorer_data.json').read_text());d['coverage_source']['source_sha256']='b'*64;self.put('explorer_data.json',d);self.assertEqual(load_research(self.d)['status'],'UNAVAILABLE')
    def test_source_uses_published_issuer_url_not_accession_prefix(self):
        p=self.d/'why/AMD.html';url='https://www.sec.gov/Archives/edgar/data/2488/000123456726000001/doc.xml';p.write_text('<a href="'+url+'">SEC</a><a href="javascript:alert(1)">bad</a>');self.assertEqual(source_links(p),{'000123456726000001':url})
    def test_unavailable_receipts_are_not_zero(self):
        h=render(None,'INVALID');self.assertIn('UNAVAILABLE',h);self.assertNotIn('attempts=0',h);self.assertNotIn('>0</strong>',h)

class FinancialNotes(unittest.TestCase):
    def setUp(self):self.notes={n['ticker']:n for n in load_notes(ROOT/'docs')['notes']}
    def vals(self,t):return {f['label']:Decimal(str(f['value'])) for f in self.notes[t]['facts']}
    def test_chevron_cash_flow_bridge(self):
        v=self.vals('CVX');self.assertEqual(v['Operating cash flow']-v['Capital expenditures'],v['Free cash flow']);self.assertEqual(v['Free cash flow']+v['Working-capital adjustment']+v['Asset proceeds / capital returned']+v['Affiliate loan repayments, net'],v['Adjusted free cash flow']);self.assertEqual(v['Adjusted free cash flow']-v['Free cash flow'],Decimal('2240'))
    def test_amazon_period_units_and_margin(self):
        n=self.notes['AMZN'];v=self.vals('AMZN');self.assertEqual(n['period_end'],'2026-09-30');self.assertEqual((v['Operating income']/v['Net sales']*100).quantize(Decimal('.1')),v['Operating margin']);self.assertTrue(all(f['unit']=='USD millions' for f in n['facts'][:2]))
    def test_exxon_rounded_distribution_sum(self):
        v=self.vals('XOM');self.assertEqual(v['Dividends']+v['Repurchases'],Decimal('9.4'))
    def test_notes_escape_untrusted_text(self):
        n=dict(self.notes['AMZN']);n['title']='</script><img onerror=alert(1)>';h=note_card(n);self.assertNotIn('<img',h);self.assertIn('&lt;img',h)
    def test_notes_are_separate_from_receipt_status(self):
        self.assertEqual(len(self.notes),4);self.assertTrue(all(n['independent_review']=='Not established' for n in self.notes.values()))

if __name__=='__main__':unittest.main()
