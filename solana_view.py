"""Expose real Solana observations even when no wallet passes the copy evidence floor."""
import json,copy
from pathlib import Path

def attach(out,root):
 from pipeline import account
 from research import empty_account
 root=Path(root);cfg=json.loads((root/'config.json').read_text());trades=[t for t in json.loads((root/'data/observations.json').read_text()) if t.get('chain','solana')=='solana'];context=json.loads((root/'data/chain-context.json').read_text()).get('solana',{});base=copy.deepcopy(cfg);base['features']['copy_trade_ranking']=False
 rows,excluded=account(trades,context.get('liquidity',{}),base,'solana');existing={w['key']:w for w in out['wallets']}
 for r in rows:
  r['experimental_score']=r['score'];r['qualified']=bool(r['qualified'] and r['hold_window_pass'] and r['mean_liquidity_usd']>=cfg['minimum_liquidity_usd'] and r['score_breakdown']['copy_capture_samples']>=cfg['minimum_closed_samples']);r['score']=existing.get(r['key'],{}).get('score') if r['qualified'] else None;r['score_mode']='copy_trade' if cfg['features']['copy_trade_ranking'] else 'basic';r['score_label']=str(r['score']) if r['qualified'] else 'Not enough data';r['disposition']='observation_only' if not r['qualified'] else 'qualified_sample_only';r['copy_simulation']=existing.get(r['key'],{}).get('copy_simulation',empty_account(cfg,out['updated_at_et'],'Observation only: not enough history to qualify for copying.'));r['standout']=False
 rows.sort(key=lambda r:(r['qualified'],r['sampled_swaps'],r['matched_sell_samples']),reverse=True)
 profiles=json.loads((root/'agents.json').read_text());sol_profiles=[p for p in profiles if p['chain']=='solana'];from research import hunt
 hunters,_=hunt(sol_profiles,rows,trades,{},cfg,out['updated_at_et']);prior={h['id']:h for h in out['agents']}
 for h in hunters:
  if h['id'] in prior:h['copy_simulation']=prior[h['id']]['copy_simulation']
 out['agents']=hunters+[a for a in out['agents'] if a['chain']!='solana'];out['stats']['solana_hunters_with_observations']=sum(a['observation_count']>0 for a in hunters)
 out['solana_observation_queue']=rows;out['stats']['solana_observation_wallets']=len(rows);out['default_chain']='solana';(root/'data/wallets.json').write_text(json.dumps(out,indent=2,allow_nan=False));(root/'data/hunting-results.json').write_text(json.dumps(out['agents'],indent=2,allow_nan=False));return out
if __name__=='__main__':
 root=Path(__file__).resolve().parent;out=attach(json.loads((root/'data/wallets.json').read_text()),root);print('Published real Solana observations:',len(out['solana_observation_queue']))
