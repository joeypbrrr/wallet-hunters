import unittest,sys,json,copy,datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import account,clusters
CFG=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())
A='11111111111111111111111111111111';B='22222222222222222222222222222222'
def trade(i,kind,qty,usd,seconds,w=A,token='TOK'):
 return {'id':str(i),'kind':kind,'quantity':qty,'usd':usd,'time':(dt.datetime(2026,11,1,tzinfo=dt.timezone.utc)+dt.timedelta(seconds=seconds)).isoformat(),'wallet':w,'token':token,'tx':str(i),'anomalous':False}
class PipelineTest(unittest.TestCase):
 def test_unknown_basis_not_profit(self):
  r,e=account([trade(1,'sell',5,100,3600)],{'TOK':100000},CFG);self.assertIsNone(r[0]['observed_realized_pnl_usd']);self.assertEqual(r[0]['unmatched_sells'],1)
 def test_fifo_and_partial_sell(self):
  r,e=account([trade(1,'buy',10,100,0),trade(2,'sell',5,75,7200)],{'TOK':100000},CFG);self.assertEqual(r[0]['observed_realized_pnl_usd'],25);self.assertEqual(r[0]['average_hold_seconds'],7200);self.assertTrue(r[0]['hold_window_pass']);self.assertFalse(r[0]['qualified'])
 def test_fifo_loss(self):
  r,e=account([trade(1,'buy',10,100,0),trade(2,'sell',10,80,7200)],{'TOK':100000},CFG);self.assertEqual(r[0]['observed_realized_pnl_usd'],-20);self.assertEqual(r[0]['win_rate_pct'],0)
 def test_copy_filters_short_and_long_unknown(self):
  cfg=copy.deepcopy(CFG);cfg['features']['copy_trade_ranking']=True
  for seconds in [9,3599,604801]:
   r,e=account([trade(1,'buy',10,100,0),trade(2,'sell',10,200,seconds)],{'TOK':100000},cfg);self.assertEqual(len(r),0);self.assertEqual(len(e),1)
 def test_copy_capture_3x(self):
  cfg=copy.deepcopy(CFG);cfg['features']['copy_trade_ranking']=True
  ts=[trade(1,'buy',10,100,0),trade(2,'buy',1,10.5,60,B),trade(3,'sell',10,300,7200)]
  r,e=account(ts,{'TOK':100000},cfg);a=next(x for x in r if x['wallet']==A);b=a['score_breakdown'];self.assertEqual(b['big_move_3x_hit_rate'],100);self.assertEqual(b['copy_capture_35_pct'],100);self.assertEqual(b['copy_capture_50_pct'],100)
 def test_missing_copy_path_unknown(self):
  cfg=copy.deepcopy(CFG);cfg['features']['copy_trade_ranking']=True
  r,e=account([trade(1,'buy',10,100,0),trade(2,'sell',10,300,7200)],{'TOK':100000},cfg);self.assertIsNone(r[0]['score_breakdown']['copy_capture_35_pct']);self.assertIsNone(r[0]['score'])
 def test_direct_cluster_keeps_members(self):
  r,e=account([trade(1,'buy',1,10,0,A),trade(2,'buy',1,10,2,B)],{'TOK':100000},CFG);c=clusters(r,[],[{'from':A,'to':B}]);self.assertEqual(len(c),1);self.assertEqual(len(c[0]['members']),2);self.assertEqual(len(r),2)
 def test_all_optional_flags_off(self):self.assertFalse(any(CFG['features'].values()))
 def test_tier_never_claims_insider(self):
  cfg=copy.deepcopy(CFG);cfg['features']['wallet_tiers']=True
  r,e=account([trade(1,'buy',10,100,0),trade(2,'sell',10,300,7200)],{'TOK':100000},cfg);self.assertEqual(r[0]['tier'],'unverified')
if __name__=='__main__':unittest.main()
