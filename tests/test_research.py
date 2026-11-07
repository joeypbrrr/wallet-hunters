import unittest,json,copy,datetime as dt,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research import simulate,decode_swap,hash_topic,V2_SIG,V3_SIG,hunt,CHAINS
ROOT=Path(__file__).resolve().parents[1];CFG=json.loads((ROOT/'config.json').read_text());PROFILES=json.loads((ROOT/'agents.json').read_text())
A='11111111111111111111111111111111';B='22222222222222222222222222222222'
def tick(i,sec,price,w=B,kind='buy',token='TOK'):
 return {'id':str(i),'chain':'solana','time':(dt.datetime(2026,11,6,12,tzinfo=dt.timezone.utc)+dt.timedelta(seconds=sec)).isoformat(),'wallet':w,'kind':kind,'quantity':1,'usd':price,'token':token,'tx':str(i),'pool':'pool'}
def row():return {'chain':'solana','wallet':A,'key':'solana:'+A,'mean_liquidity_usd':100000,'qualified':False}
class ResearchTest(unittest.TestCase):
 def test_50_real_unique_slices(self):
  self.assertEqual(len(PROFILES),50);self.assertEqual(len({p['id'] for p in PROFILES}),50);self.assertEqual(len({p['name'] for p in PROFILES}),50)
  self.assertEqual(len({json.dumps([p['chain'],p['slice']],sort_keys=True) for p in PROFILES}),50)
  self.assertEqual([sum(p['chain']==c for p in PROFILES) for c in ['solana','bsc','robinhood']],[30,15,5]);self.assertNotIn('ethereum',CHAINS)
 def test_v2_decode(self):
  log={'topics':[hash_topic(V2_SIG)],'data':'0x'+''.join(f'{n:064x}' for n in [100,0,0,200])};j=decode_swap(log);self.assertEqual(j['amount0_in_raw'],100);self.assertEqual(j['amount1_out_raw'],200)
 def test_v3_signed_decode(self):
  log={'topics':[hash_topic(V3_SIG)],'data':'0x'+''.join(f'{n%(2**256):064x}' for n in [-123,456,100,200,-3])};j=decode_swap(log);self.assertEqual(j['amount0_delta_raw'],-123);self.assertEqual(j['tick'],-3)
 def test_no_future_peak_execution(self):
  # Pre-delay peak is not capturable; source later sells at a loss.
  ts=[tick(1,0,10,A),tick(2,5,30),tick(3,60,10),tick(4,7200,8,A,'sell')];s=simulate(row(),ts,CFG,'now');self.assertEqual(s['closed_trades'],1);self.assertLess(s['realized_pnl_usd'],0);self.assertGreater(s['fills'][0]['fees_usd'],0);self.assertIsNone(s['expected_profit_per_day_usd'])
 def test_finite_cash_and_missing_price(self):
  s=simulate(row(),[tick(1,0,10,A),tick(2,600,20,A,'sell')],CFG,'now');self.assertEqual(s['trades'],0);self.assertEqual(s['balance_usd'],500)
 def test_first_target_not_best_peak(self):
  ts=[tick(1,0,10,A),tick(2,60,10),tick(3,7200,16),tick(4,7500,50)];s=simulate(row(),ts,CFG,'now');self.assertEqual(s['fills'][0]['exit_observation'],'3');self.assertLess(s['realized_pnl_usd'],100)
 def test_entry_stop_manage_open_and_restart_dedup(self):
  c=copy.deepcopy(CFG);c['daily_profit_goal_usd']=1
  ts=[tick(1,0,10,A,token='A'),tick(2,10,10,A,token='B'),tick(3,60,10,token='A'),tick(4,70,10,token='B'),tick(5,7200,16,token='A'),tick(6,7210,10,A,token='C'),tick(7,7270,10,token='C'),tick(8,7300,16,token='B')]
  a=simulate(row(),ts,c,'now');b=simulate(row(),ts,c,'now');self.assertEqual(a['closed_trades'],2);self.assertEqual(a['fills'],b['fills']);self.assertGreaterEqual(a['skipped']['daily_stop'],1);self.assertEqual(a['open_positions'],0)
 def test_hunt_no_candidates_runs_all_50(self):
  out,keys=hunt(PROFILES,[],[],{},CFG,'now');self.assertEqual(len(out),50);self.assertTrue(all(h['status']=='completed_no_match' for h in out));self.assertFalse(keys)
if __name__=='__main__':unittest.main()

class StateAndEvidenceTest(unittest.TestCase):
 def test_missing_usd_not_zero_profit(self):
  from pipeline import account
  cfg=copy.deepcopy(CFG);cfg['features']['copy_trade_ranking']=False
  t=tick(1,0,0,A);rows,_=account([t],{'TOK':100000},cfg)
  self.assertIsNone(rows[0]['observed_realized_pnl_usd']);self.assertEqual(rows[0]['matched_sell_samples'],0)
 def test_loss_review_deduplicates_and_never_auto_applies(self):
  from research import build_learning
  s=simulate(row(),[tick(1,0,10,A),tick(2,60,10),tick(3,7200,8,A,'sell')],CFG,'now')
  a=build_learning({row()['key']:s},{},CFG,'now');b=build_learning({row()['key']:s},a,CFG,'now')
  self.assertEqual(len(b['reviews']),1);self.assertTrue(all(not l['automatically_applied'] for l in b['lessons']))
 def test_agent_selection_persists_and_does_not_retrofill(self):
  from tempfile import TemporaryDirectory
  from agent_accounts import attach
  with TemporaryDirectory() as directory:
   root=Path(directory);(root/'data').mkdir();(root/'config.json').write_text(json.dumps(CFG));(root/'data/observations.json').write_text(json.dumps([tick(1,0,10,A),tick(2,60,10),tick(3,7200,16,A,'sell')]))
   a=row();b={**row(),'key':'solana:'+B,'wallet':B}
   out={'wallets':[a,b],'agents':[{'id':'test-agent','best_wallet':{'key':a['key']}}],'updated_at_et':'now','daily_goal':{},'stats':{}}
   attach(out,root);first=json.loads((root/'data/agent-account-state.json').read_text());out['agents'][0]['best_wallet']={'key':b['key']};attach(out,root);second=json.loads((root/'data/agent-account-state.json').read_text())
   self.assertEqual(first['test-agent']['selected_at'],second['test-agent']['selected_at']);self.assertEqual(second['test-agent']['selected_wallet'],a['key']);self.assertEqual(out['agents'][0]['copy_simulation']['closed_trades'],0);self.assertEqual(out['agents'][0]['copy_simulation']['balance_usd'],500)
