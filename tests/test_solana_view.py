"""Synthetic unit fixtures only: never published as real wallet data."""
import copy,json,tempfile,unittest
from pathlib import Path
from solana_view import attach
ROOT=Path(__file__).resolve().parents[1]
class SolanaViewTest(unittest.TestCase):
 def test_unqualified_unknown_score_links_and_forward_account_preserved(self):
  cfg=json.loads((ROOT/'config.json').read_text());profiles=json.loads((ROOT/'agents.json').read_text());sol=[p for p in profiles if p['chain']=='solana'];wallet='W'*44
  trades=[{'id':str(i),'chain':'solana','wallet':wallet,'token':'TEST_TOKEN_NOT_REAL','kind':kind,'quantity':1,'usd':usd,'time':time,'tx':'TEST_TX_NOT_REAL','pool':'TEST_POOL_NOT_REAL'} for i,kind,usd,time in [(1,'buy',10,'2026-10-01T00:00:00Z'),(2,'sell',20,'2026-10-01T02:00:00Z')]]
  prior=[dict(p,copy_simulation={'mode':'forward_observation_paper','balance_usd':500,'sentinel':'preserve'}) for p in sol];out={'wallets':[],'agents':prior,'stats':{},'updated_at_et':'TEST timestamp'}
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'data').mkdir()
   for name,value in [('config.json',cfg),('agents.json',profiles),('data/observations.json',trades),('data/chain-context.json',{'solana':{'liquidity':{'TEST_TOKEN_NOT_REAL':100000}}})]:(root/name).write_text(json.dumps(value))
   result=attach(copy.deepcopy(out),root);r=result['solana_observation_queue'][0]
   self.assertIsNone(r['score']);self.assertEqual(r['score_label'],'Not enough data');self.assertFalse(r['qualified']);self.assertEqual(r['chain'],'solana');self.assertIn('/sol/address/',r['gmgn']);self.assertIn('solscan.io/account/',r['explorer']);self.assertEqual(len(result['agents']),30)
   for h in result['agents']:self.assertEqual(h['copy_simulation']['sentinel'],'preserve')
   self.assertEqual(sum(h['observation_count'] for h in result['agents']),1)
   self.assertEqual(json.loads((root/'data/hunting-results.json').read_text()),result['agents'])
