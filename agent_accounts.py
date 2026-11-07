"""Durable, independent $500 forward-observation paper accounts for all fifty hunters."""
import json,datetime as dt
from pathlib import Path
from research import simulate,empty_account,et

def attach(out,root):
 root=Path(root);cfg=json.loads((root/'config.json').read_text());trades=json.loads((root/'data/observations.json').read_text());statepath=root/'data/agent-account-state.json'
 try:state=json.loads(statepath.read_text())
 except FileNotFoundError:state={}
 now=dt.datetime.now(dt.timezone.utc).isoformat();rows={w['key']:w for w in out['wallets']};accounts={}
 for h in out['agents']:
  entry=state.setdefault(h['id'],{'created_at':now,'selected_wallet':None})
  if not entry['selected_wallet'] and h.get('best_wallet'):
   key=h['best_wallet']['key'];row=rows.get(key)
   if row:entry.update({'selected_wallet':key,'selected_at':now,'wallet_metadata':{k:row[k] for k in ['key','wallet','chain','mean_liquidity_usd','qualified']}})
  row=rows.get(entry['selected_wallet'],entry.get('wallet_metadata'))
  sim=simulate(row,trades,cfg,out['updated_at_et'],entry_start_at=entry['selected_at']) if row else empty_account(cfg,out['updated_at_et'],'Waiting for this hunter’s first real slice match; no fabricated fills.')
  sim.update({'account_id':h['id'],'mode':'forward_observation_paper','copied_wallet':entry['selected_wallet'],'created_at_et':et(entry['created_at']),'selected_at_et':et(entry['selected_at']) if entry.get('selected_at') else None})
  h['copy_simulation']=sim;accounts[h['id']]=sim
 statepath.write_text(json.dumps(state,indent=2));(root/'data/agent-paper-accounts.json').write_text(json.dumps(accounts,indent=2));out['daily_goal']['agent_accounts']=[{'agent_id':k,'realized_today_usd':v['today_realized_pnl_usd'],'goal_hit':v['goal_hit'],'remaining_usd':max(0,cfg['daily_profit_goal_usd']-v['today_realized_pnl_usd']),'standout':v['standout']} for k,v in accounts.items()];out['daily_goal']['scope']='Each account separately. Wallet accounts are retrospective diagnostics; hunter accounts begin only after a real slice selection and persist that selection across restarts.';out['stats']['forward_agent_closed_fills']=sum(a['closed_trades'] for a in accounts.values());out['stats']['forward_agent_open_positions']=sum(a['open_positions'] for a in accounts.values());out['stats']['forward_agent_accounts']=len(accounts)
 for filename,obj in [('wallets.json',out),('hunting-results.json',out['agents']),('daily-goals.json',out['daily_goal'])]:(root/'data'/filename).write_text(json.dumps(obj,indent=2,allow_nan=False))
 return out
if __name__=='__main__':
 root=Path(__file__).resolve().parent;out=json.loads((root/'data/wallets.json').read_text());out=attach(out,root);print('Initialized/updated',out['stats']['forward_agent_accounts'],'durable agent paper accounts; closed fills',out['stats']['forward_agent_closed_fills'])
