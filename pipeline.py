#!/usr/bin/env python3
"""Six bounded research stages. Public reads only; no signing, execution or keys."""
import json, math, time, statistics, re, collections, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
ET=ZoneInfo('America/New_York')
AGENTS=[('Scout','Find liquid Solana tokens using DexScreener and trending pools using GeckoTerminal.'),('Entry Cartographer','Collect recent observed swaps; check a bounded sample against Solana RPC, not launch history.'),('PnL Accountant','FIFO-match observed buys and sells, preserving unknown cost basis and monthly coverage gaps.'),('Integrity Analyst','Flag rapid flips and suspected wash patterns; optionally group linked wallets instead of excluding clusters.'),('Copyability Ranker','Score evidence and sample confidence; optional copy-trade score adds observed early entry, hold time and liquidity.'),('Observatory Publisher','Publish evidence, source limits, ET timestamps and explorer links; schedule stays off until approved.')]
def load(p,default):
 try:return json.loads(p.read_text())
 except (FileNotFoundError,json.JSONDecodeError):return default
def save(p,obj):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2,allow_nan=False));tmp.replace(p)
def stamp():return dt.datetime.now(ET).strftime('%Y-%m-%d %I:%M:%S %p ET')
def iso():return dt.datetime.now(dt.timezone.utc).isoformat()
def get(url):
 r=requests.get(url,timeout=22,headers={'User-Agent':'WalletHunters/1.0 public research'});r.raise_for_status();return r.json()
def rpc(method,params=[]):
 r=requests.post('https://api.mainnet-beta.solana.com',json={'jsonrpc':'2.0','id':1,'method':method,'params':params},timeout=22);r.raise_for_status();j=r.json()
 if 'error' in j:raise RuntimeError(str(j['error']))
 return j.get('result')
def wallet_ok(w):return bool(re.fullmatch('[1-9A-HJ-NP-Za-km-z]{32,44}',w or ''))
def num(v):
 try:return float(v or 0)
 except (TypeError,ValueError):return 0

def simulation_account(cfg):
 return {'enabled':cfg['features'].get('copy_account_simulation',False),'status':'in_progress','starting_balance_usd':cfg['copy_sim_starting_balance_usd'],'balance_usd':cfg['copy_sim_starting_balance_usd'],'trades':0,'expected_profit_per_day_usd':None,'capital_needed_for_300_per_day_usd':None,'reason':'$500 simulation allocation; execution/backtest engine in progress. No simulated fills yet. No complete historical execution backtest or reliable daily return; no profit forecast is justified. Six research agents do not have independent trading strategies.'}

def account(trades,liquidity,cfg):
 """Conservative observed FIFO: unmatched sells are NOT profits."""
 wallets=collections.defaultdict(list)
 for t in trades:
  if wallet_ok(t.get('wallet')):wallets[t['wallet']].append(t)
 rows=[];excluded=[]
 for w,ts in wallets.items():
  ts.sort(key=lambda t:(t['time'],t['id']));lots=collections.defaultdict(collections.deque);closed=[];unknown=0;month_vol=collections.defaultdict(float);turnover=0;quick=0
  for t in ts:
   token=t['token'];q=t['quantity'];usd=t['usd'];month=dt.datetime.fromisoformat(t['time'].replace('Z','+00:00')).astimezone(ET).strftime('%Y-%m');turnover+=usd;month_vol[month]+=usd
   if q<=0:continue
   if t['kind']=='buy':lots[token].append([q,usd/q,t['time']])
   elif t['kind']=='sell':
    remain=q;profit=0;matched=0;holds=[]
    while remain>1e-12 and lots[token]:
     l=lots[token][0];take=min(remain,l[0]);profit+=take*(usd/q-l[1]);matched+=take
     hold=(dt.datetime.fromisoformat(t['time'].replace('Z','+00:00'))-dt.datetime.fromisoformat(l[2].replace('Z','+00:00'))).total_seconds();holds.append((max(0,hold),take));l[0]-=take;remain-=take
     if l[0]<=1e-12:lots[token].popleft()
    if remain>max(1e-8,q*1e-6):unknown+=1
    if matched:
     hold=sum(h*n for h,n in holds)/matched
     closed.append({'time':t['time'],'month':month,'pnl':profit,'hold_seconds':hold,'token':token,'tx':t['tx'],'buy_time':(dt.datetime.fromisoformat(t['time'].replace('Z','+00:00'))-dt.timedelta(seconds=hold)).isoformat()})
  n=len(closed);wins=sum(x['pnl']>0 for x in closed);pnl=sum(x['pnl'] for x in closed);holds=[x['hold_seconds'] for x in closed];median=statistics.median(holds) if holds else None
  avg_hold=statistics.mean(holds) if holds else None
  hold_eligible=avg_hold is not None and cfg['min_avg_hold_seconds']<=avg_hold<=cfg['max_avg_hold_seconds']
  lq=statistics.mean([liquidity.get(t['token'],0) for t in ts]) if ts else 0
  per_min=collections.Counter(t['time'][:16] for t in ts)
  flags=[]
  if max(per_min.values(),default=0)>60:flags.append('high-frequency activity (>60 sampled swaps/minute); possible automation')
  if n>=5 and median is not None and median<2:flags.append('sub-2-second matched holds; possible MEV/sniper')
  if len(ts)>=20 and sum(t.get('anomalous',False) for t in ts)/len(ts)>.5:flags.append('majority anomalous swaps; possible wash pattern')
  # Heuristics do not prove MEV or manipulation. Exclusions are auditable.
  if cfg['features']['copy_trade_ranking'] and lq<cfg['minimum_liquidity_usd']:flags.append('copy liquidity below $25k or unavailable')
  if cfg['features']['copy_trade_ranking'] and not hold_eligible:flags.append('copy window: observed average hold outside 1 hour–1 week, or unknown')
  if flags:excluded.append({'wallet':w,'reasons':flags});continue
  months=collections.defaultdict(float)
  for x in closed:months[x['month']]+=x['pnl']
  history=[{'month':m,'observed_realized_pnl_usd':round(v,4),'partial':True} for m,v in sorted(months.items())]
  wr=wins/n*100 if n else None;positive=sum(v>0 for v in months.values());negative=sum(v<0 for v in months.values())
  # Never treat a partial current month as proof of consistent monthly profits.
  min_n=cfg['minimum_closed_samples'];min_m=cfg['minimum_observed_months']
  qualified=n>=min_n and len(months)>=min_m and all(v>0 for v in months.values())
  conf=min(1,n/min_n)*min(1,len(months)/min_m)
  profit_component=min(100,max(0,50+10*math.log1p(abs(pnl))*(1 if pnl>=0 else -1))) if n else None
  basic=round((.65*(wr or 0)+.35*(profit_component or 0))*conf,2) if n else None
  # Evaluate only observed matched holding windows. Weighted FIFO buy time is approximate.
  big=[];capture35=[];capture50=[]
  lq=statistics.mean([liquidity.get(t['token'],0) for t in ts]) if ts else 0
  for c in closed:
   if not cfg['min_avg_hold_seconds']<=c['hold_seconds']<=cfg['max_avg_hold_seconds']:continue
   buy_at=dt.datetime.fromisoformat(c['buy_time']);end_at=dt.datetime.fromisoformat(c['time'].replace('Z','+00:00'))
   window=[x for x in trades if x['token']==c['token'] and x['quantity']>0 and buy_at<=dt.datetime.fromisoformat(x['time'].replace('Z','+00:00'))<=end_at]
   window.sort(key=lambda x:x['time'])
   if not window:continue
   original=window[0]['usd']/window[0]['quantity']
   if original<=0:continue
   peak=max(x['usd']/x['quantity'] for x in window)
   big.append(peak/original>=cfg['big_move_multiple'])
   target=buy_at+dt.timedelta(seconds=cfg['copy_delay_seconds'])
   entries=[x for x in window if target<=dt.datetime.fromisoformat(x['time'].replace('Z','+00:00'))<=target+dt.timedelta(seconds=cfg['copy_entry_max_gap_seconds'])]
   if not entries or lq<=0:continue
   entry=entries[0];later=[x for x in window if x['time']>entry['time']]
   if not later:continue
   impact=min(.5,cfg['copy_order_usd']/lq);slip=cfg['copy_slippage_pct']/100+impact
   paid=entry['usd']/entry['quantity']*(1+slip)
   best=max(x['usd']/x['quantity'] for x in later)*(1-slip)
   net=(best/paid-1)*100
   capture35.append(net>=cfg['copy_capture_targets_pct'][0]);capture50.append(net>=cfg['copy_capture_targets_pct'][1])
  big_rate=sum(big)/len(big)*100 if big else None
  cap35=sum(capture35)/len(capture35)*100 if capture35 else None
  cap50=sum(capture50)/len(capture50)*100 if capture50 else None
  early_score=big_rate
  hold_score=min(100,(avg_hold or 0)/86400*100)
  liq_score=min(100,lq/cfg['minimum_liquidity_usd']*50)
  consistency=positive/len(months)*100 if months else None
  breakdown={'win_rate':wr,'big_move_3x_hit_rate':big_rate,'big_move_samples':len(big),'copy_capture_35_pct':cap35,'copy_capture_50_pct':cap50,'copy_capture_samples':len(capture35),'monthly_consistency':consistency,'follower_hold_time':hold_score if n else None,'average_hold_seconds':avg_hold,'median_hold_seconds':median,'hold_window_pass':hold_eligible,'liquidity':liq_score,'sample_confidence':round(conf,4),'entry_market_cap':None,'historical_peak':None}
  weights={'win_rate':.25,'big_move_3x_hit_rate':.20,'copy_capture_35_pct':.20,'copy_capture_50_pct':.10,'monthly_consistency':.15,'follower_hold_time':.05,'liquidity':.05}
  copy=round(sum((breakdown[k] or 0)*v for k,v in weights.items())*conf,2) if n and hold_eligible and capture35 else None
  mode='copy_trade' if cfg['features']['copy_trade_ranking'] else 'basic'
  score=copy if mode=='copy_trade' else basic
  if cfg['features']['consistency_score'] and mode=='basic' and n:score=round(.8*score+.2*(consistency or 0)*conf,2)
  row={'wallet':w,'score':score,'score_mode':mode,'score_breakdown':breakdown,'copy_score_weights':weights,'qualified':qualified,'status':'qualified_sample_only' if qualified else 'insufficient_history','sampled_swaps':len(ts),'matched_sell_samples':n,'wins':wins,'win_rate_pct':round(wr,2) if wr is not None else None,'observed_realized_pnl_usd':round(pnl,4) if n else None,'pnl_30d_usd':round(sum(x['pnl'] for x in closed if x['time']>=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=30)).isoformat()),4) if n else None,'unmatched_sells':unknown,'average_hold_seconds':round(avg_hold,2) if avg_hold is not None else None,'hold_window_pass':hold_eligible,'median_hold_seconds':round(median,2) if median is not None else None,'mean_liquidity_usd':round(lq,2),'observed_months':len(months),'positive_months':positive,'negative_months':negative,'monthly_history':history,'gmgn':f'https://gmgn.ai/sol/address/{w}','solscan':f'https://solscan.io/account/{w}','copy_simulation':simulation_account(cfg),'standout':False,'cluster_id':None,'tier':None,'notes':['Provider-reported wallet; RPC attribution is sampled.','Observed matched sells, not full-wallet P&L. Fees/MEV/transfers not included.']}
  if cfg['features']['wallet_tiers']:
   row['tier']='unverified'
   if qualified and wr>=65 and median>=60 and lq>=cfg['minimum_liquidity_usd']:row['tier']='sharp'
   if qualified and pnl>=10000:row['tier']='whale (observed profit)'
   if qualified and early_score is not None and early_score>=50 and median>=60:row['tier']='early-entry (not proof of insider)'
  rows.append(row)
 rows.sort(key=lambda r:(r['qualified'],r['score'] if r['score'] is not None else -1,r['sampled_swaps']),reverse=True)
 return rows,excluded

def clusters(rows,trades,transfers):
 """Evidence-based heuristic grouping; a link is not proof of common ownership."""
 ws={r['wallet'] for r in rows};parents={w:w for w in ws};edges=[]
 def root(w):
  while parents[w]!=w:w=parents[w]
  return w
 def link(a,b,reason):
  if a in ws and b in ws and a!=b:parents[root(a)]=root(b);edges.append({'a':a,'b':b,'reason':reason})
 funders=collections.defaultdict(set)
 for t in transfers:
  if t['to'] in ws:funders[t['from']].add(t['to'])
  link(t['from'],t['to'],'RPC-observed SOL transfer (may be unrelated)')
 for f,members in funders.items():
  # Avoid obvious omnibus-funder explosion; explicitly limited evidence.
  if 2<=len(members)<=10:
   members=sorted(members)
   for b in members[1:]:link(members[0],b,'same RPC-observed funding source '+f)
 buys=collections.defaultdict(list)
 for t in trades:
  if t['kind']=='buy' and t['wallet'] in ws:buys[t['token']].append(t)
 pairs=collections.defaultdict(set)
 for token,ts in buys.items():
  ts.sort(key=lambda x:x['time'])
  for i,a in enumerate(ts):
   for b in ts[i+1:i+16]:
    delta=(dt.datetime.fromisoformat(b['time'].replace('Z','+00:00'))-dt.datetime.fromisoformat(a['time'].replace('Z','+00:00'))).total_seconds()
    if delta>3:break
    if a['wallet']!=b['wallet']:pairs[tuple(sorted([a['wallet'],b['wallet']]))].add(token)
 for (a,b),tokens in pairs.items():
  if len(tokens)>=3:link(a,b,'co-buys within 3 seconds across at least 3 observed tokens')
 groups=collections.defaultdict(list)
 for r in rows:groups[root(r['wallet'])].append(r)
 result=[]
 for members in groups.values():
  if len(members)<2:continue
  import hashlib
  cid='C-'+hashlib.sha256('|'.join(sorted(r['wallet'] for r in members)).encode()).hexdigest()[:8]
  for r in members:r['cluster_id']=cid
  n=sum(r['matched_sell_samples'] for r in members);wins=sum(r['wins'] for r in members)
  result.append({'cluster_id':cid,'members':[{'wallet':r['wallet'],'gmgn':r['gmgn'],'solscan':r['solscan']} for r in members],'matched_sell_samples':n,'win_rate_pct':round(wins/n*100,2) if n else None,'observed_realized_pnl_usd':round(sum(r['observed_realized_pnl_usd'] or 0 for r in members),4) if n else None,'score':round(sum((r['score'] or 0)*r['matched_sell_samples'] for r in members)/n,2) if n else None,'warning':'Heuristic link, not confirmed ownership. Summed observed member P&L may double count inter-wallet economic exposure.','evidence':[e for e in edges if e['a'] in {r['wallet'] for r in members} and e['b'] in {r['wallet'] for r in members}]})
 return sorted(result,key=lambda r:r['score'] or -1,reverse=True)

def run():
 cfg=load(ROOT/'config.json',{});chat=[];errors=[];sources=[]
 def say(a,m):chat.append({'agent':a,'time_et':stamp(),'text':m});print(a+': '+m,flush=True)
 say('Scout','Starting one keyless, read-only research cycle; no trades or external alerts.')
 dex=[];pools=[];liq={};symbols={}
 try:
  dex=get('https://api.dexscreener.com/latest/dex/search?q=SOL').get('pairs',[]);dex=[p for p in dex if p.get('chainId')=='solana'];sources.append({'name':'DexScreener','status':'ok','pairs':len(dex)})
 except Exception as e:errors.append('DexScreener: '+str(e))
 try:
  pools=get('https://api.geckoterminal.com/api/v2/networks/solana/trending_pools?include=base_token').get('data',[])[:cfg['pool_limit']];sources.append({'name':'GeckoTerminal trending pools','status':'ok','pools':len(pools)})
 except Exception as e:errors.append('GeckoTerminal: '+str(e))
 observed=[];tokens=set();pool_ok=0
 for p in pools:
  a=p['attributes'];token=p.get('relationships',{}).get('base_token',{}).get('data',{}).get('id','').removeprefix('solana_')
  if not token:continue
  tokens.add(token);liq[token]=num(a.get('reserve_in_usd'));symbols[token]=a.get('name','')
  try:
   time.sleep(2.1)
   ts=get(f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{a['address']}/trades").get('data',[]);pool_ok+=1
   for item in ts:
    t=item['attributes'];buy=t['kind']=='buy';qty=num(t.get('to_token_amount' if buy else 'from_token_amount'))
    observed.append({'id':item['id'],'wallet':t.get('tx_from_address'),'token':token,'kind':t['kind'],'quantity':qty,'usd':num(t.get('volume_in_usd')),'time':t['block_timestamp'],'tx':t['tx_hash'],'pool':a['address'],'anomalous':t.get('is_anomalous',False)})
  except Exception as e:errors.append(a['address']+': '+str(e))
 say('Scout',f'Found {len(dex)} DexScreener pairs and {len(tokens)} GeckoTerminal tokens; fetched {pool_ok} pool trade windows.')
 say('Entry Cartographer',f'Collected {len(observed)} recent provider-reported swaps. Earliest observed is NOT earliest launch buyer.')
 transfers=[];checked=0;attribution=[]
 try:
  slot=rpc('getSlot');sources.append({'name':'Solana public RPC','status':'ok','slot':slot})
  for tx in list(dict.fromkeys(t['tx'] for t in observed))[:cfg['rpc_transaction_limit']]:
   time.sleep(1.2)
   try:
    j=rpc('getTransaction',[tx,{'encoding':'jsonParsed','maxSupportedTransactionVersion':0}])
    if not j:continue
    checked+=1;signers=[k['pubkey'] for k in j['transaction']['message']['accountKeys'] if isinstance(k,dict) and k.get('signer')];attribution.append({'tx':tx,'signers':signers})
    instructions=list(j['transaction']['message'].get('instructions',[]))
    for ins in j.get('meta',{}).get('innerInstructions',[]):instructions+=ins.get('instructions',[])
    for ins in instructions:
     parsed=ins.get('parsed',{});info=parsed.get('info',{}) if isinstance(parsed,dict) else {}
     if ins.get('program')=='system' and parsed.get('type')=='transfer' and info.get('source') and info.get('destination'):transfers.append({'from':info['source'],'to':info['destination'],'lamports':info.get('lamports'),'tx':tx})
   except Exception as e:errors.append('RPC transaction: '+str(e));break
 except Exception as e:errors.append('RPC: '+str(e))
 say('Entry Cartographer',f'RPC inspected {checked} transactions; captured {len(transfers)} SOL-transfer edges. Unchecked attribution remains provider reported.')
 previous=load(DATA/'observations.json',[]);known={t['id'] for t in previous};new=[t for t in observed if t['id'] not in known]
 # Gecko ID includes pool/index: event IDs are preferred over tx-only dedup so multi-swap transactions remain intact.
 all_trades=list({t['id']:t for t in previous+observed}.values());save(DATA/'observations.json',all_trades);save(DATA/'market-context.json',{'liquidity':liq,'sources':sources,'transfers':transfers})
 rows,excluded=account(all_trades,liq,cfg)
 say('PnL Accountant',f'Observed {len({t["wallet"] for t in all_trades if wallet_ok(t.get("wallet"))})} wallets; FIFO matched {sum(r["matched_sell_samples"] for r in rows)} sell samples. Unknown starting inventory excluded, fees not known.')
 grouped=clusters(rows,all_trades,transfers) if cfg['features']['cluster_detection'] else []
 say('Integrity Analyst',f'Excluded {len(excluded)} heuristic bot/wash candidates; clusters '+(f'enabled: {len(grouped)} groups.' if cfg['features']['cluster_detection'] else 'OFF. No insider claim is made.'))
 qualified=sum(r['qualified'] for r in rows)
 say('Copyability Ranker',f'{qualified} wallets meet minimum evidence ({cfg["minimum_closed_samples"]} matched sells, {cfg["minimum_observed_months"]} observed positive months); all others are a provisional observation queue. '+('Copy score ON.' if cfg['features']['copy_trade_ranking'] else 'Basic ranking; copy score OFF.'))
 top={r['wallet'] for r in rows[:10]};alerts=load(DATA/'alerts.json',[])
 if cfg['features']['new_buy_alert_feed']:
  for t in (new if previous else []):
   if t['kind']=='buy' and t['wallet'] in top:alerts.append({'id':t['id'],'wallet':t['wallet'],'token':t['token'],'observed_at_et':stamp(),'block_time':t['time'],'usd':t['usd'],'solscan':f"https://solscan.io/tx/{t['tx']}",'text':'Newly observed buy in sampled feed; not a real-time or complete-wallet alert.'})
  save(DATA/'alerts.json',alerts[-200:])
 say('Observatory Publisher','Publishing research snapshots and ET timestamps. Hourly publishing configured ON; chain feed is a timestamped static snapshot. Simulator/learning/goal-board features are visibly in progress; no invented fills or forecasts.')
 out={'updated_at':iso(),'updated_at_et':stamp(),'copy_simulation':simulation_account(cfg),'schedule':('ON: local hourly research publisher' if cfg.get('hourly_enabled') else 'OFF'),'features':cfg['features'],'thresholds':{k:v for k,v in cfg.items() if k!='features'},'agents':[{'name':n,'role':r,'copy_simulation':simulation_account(cfg)} for n,r in AGENTS],'stats':{'dex_pairs_scanned':len(dex),'tokens_scanned':len(tokens),'pools_with_trades':pool_ok,'swaps_this_cycle':len(observed),'new_swaps':len(new),'wallets_scanned':len({t['wallet'] for t in all_trades if wallet_ok(t.get('wallet'))}),'wallets_published':len(rows),'qualified_wallets':qualified,'hold_window_survivors':sum(r['hold_window_pass'] for r in rows),'bot_wash_exclusions':sum(any('high-frequency' in a or 'sub-2-second' in a or 'anomalous' in a for a in x['reasons']) for x in excluded),'hold_window_exclusions':sum(any('copy window' in a for a in x['reasons']) for x in excluded),'liquidity_exclusions':sum(any('copy liquidity' in a for a in x['reasons']) for x in excluded),'minimum_sell_sample_pass':sum(r['matched_sell_samples']>=cfg['minimum_closed_samples'] for r in rows),'minimum_months_pass':sum(r['observed_months']>=cfg['minimum_observed_months'] for r in rows),'qualified_copy_wallets':qualified,'excluded_wallets':len(excluded),'rpc_transactions_checked':checked},'sources':sources,'errors':errors,'limits':['Keyless feeds sample recent swaps in selected trending pools; not full-chain or full-wallet histories.','DexScreener scouts markets; GeckoTerminal supplies recent swap observations. Public RPC checks only a small transaction sample. GMGN and Solscan are links only.','Matched-sell win rates and FIFO P&L are estimates on observed lots, NOT account returns. Fees, token taxes, transfers and prior holdings omitted.','Monthly observations are partial; missing months are UNKNOWN, not zero. A few minutes of data cannot demonstrate consistent monthly profits.','No historical entry market cap or true peak is available. Copy scoring uses weighted FIFO matched holding windows and sparse observed prices, not verified insider timing. A 3x move means +200%, not +300%.','Bot and cluster heuristics are incomplete and can misclassify. No wallet is proven an insider; no guarantee of profitable copying.','Copy capture is retrospective best sampled exit, not an execution backtest. Delay, each-way slippage and current liquidity impact are configurable; no guarantee a follower captures 35–50%.','APIs are rate-limited and may omit trades. Hourly polling misses activity; first enabled alert cycle is an observation baseline.'],'wallets':rows,'clusters':grouped,'excluded':excluded,'attribution_checks':attribution,'agent_chat':chat,'alerts':alerts[-100:] if cfg['features']['new_buy_alert_feed'] else []}
 out['feature_status']={k:('in_progress' if k in ['copy_account_simulation','agent_learning','lessons_board','daily_goal_tracker','standout_badges'] else 'enabled_sampled_evidence') for k,v in cfg['features'].items() if v}
 out['learning']={'status':'in_progress','lessons':[],'note':'No simulated closed fills yet. Learning is suggestion-only; never modifies thresholds automatically.'}
 out['daily_goal']={'status':'in_progress','date_et':dt.datetime.now(ET).strftime('%Y-%m-%d'),'starting_balance_per_account_usd':cfg['copy_sim_starting_balance_usd'],'realized_copy_pnl_usd':0,'goal_usd':cfg['daily_profit_goal_usd'],'remaining_usd':cfg['daily_profit_goal_usd'],'goal_hit':False,'standout_wallets':[],'note':'Zero simulated fills; this is an initialized tracker, not source-wallet P&L. Standout requires validated net copy profit ≥$300/day, never inferred from best-price capture.'}
 out['history_probe']=load(DATA/'history-probe.json',[])
 out['observed_window']={'first_trade':min((t['time'] for t in all_trades),default=None),'last_trade':max((t['time'] for t in all_trades),default=None)}
 save(DATA/'wallets.json',out);save(DATA/'agent-chat.json',chat)
 print(json.dumps(out['stats']),flush=True)
if __name__=='__main__':run()
