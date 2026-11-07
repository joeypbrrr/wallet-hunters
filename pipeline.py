#!/usr/bin/env python3
"""Six bounded research stages. Public reads only; no signing, execution or keys."""
import json, math, time, statistics, re, collections, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import requests, copy, sys
from research import CHAINS,FetchQueue,links,verify_evm,hunt,simulate,empty_account,build_learning
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
def wallet_ok(w):return bool(re.fullmatch(r'(?:[1-9A-HJ-NP-Za-km-z]{32,44}|0x[0-9a-fA-F]{40})',w or ''))
def num(v):
 try:return float(v or 0)
 except (TypeError,ValueError):return 0

def simulation_account(cfg):
 return {'enabled':cfg['features'].get('copy_account_simulation',False),'status':'in_progress','starting_balance_usd':cfg['copy_sim_starting_balance_usd'],'balance_usd':cfg['copy_sim_starting_balance_usd'],'trades':0,'expected_profit_per_day_usd':None,'capital_needed_for_300_per_day_usd':None,'reason':'$500 simulation allocation; execution/backtest engine in progress. No simulated fills yet. No complete historical execution backtest or reliable daily return; no profit forecast is justified. Six research agents do not have independent trading strategies.'}

def account(trades,liquidity,cfg,chain='solana'):
 """Conservative observed FIFO: unmatched sells are NOT profits."""
 wallets=collections.defaultdict(list)
 for t in trades:
  if wallet_ok(t.get('wallet')):wallets[t['wallet']].append(t)
 rows=[];excluded=[]
 for w,ts in wallets.items():
  ts.sort(key=lambda t:(t['time'],t['id']));lots=collections.defaultdict(collections.deque);closed=[];unknown=0;month_vol=collections.defaultdict(float);turnover=0;quick=0
  for t in ts:
   token=t['token'];q=t['quantity'];usd=t['usd'];month=dt.datetime.fromisoformat(t['time'].replace('Z','+00:00')).astimezone(ET).strftime('%Y-%m');turnover+=usd;month_vol[month]+=usd
   if q<=0 or usd<=0:continue
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
   window=[x for x in trades if x['token']==c['token'] and x['quantity']>0 and x['usd']>0 and buy_at<=dt.datetime.fromisoformat(x['time'].replace('Z','+00:00'))<=end_at]
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
   fee=cfg.get('simulation',{}).get('fee_bps_per_side',{}).get(chain,0)/10000
   network=cfg.get('simulation',{}).get('network_fee_usd_per_side',{}).get(chain,0)
   net=(best*(1-fee)/(paid*(1+fee))-1)*100-2*network/max(1,cfg['copy_order_usd'])*100
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
  row.update({'chain':chain,'key':chain+':'+w,**links(chain,w)});row['solscan']=row['explorer']
  rows.append(row)
 rows.sort(key=lambda r:(r['qualified'],r['score'] if r['score'] is not None else -1,r['sampled_swaps']),reverse=True)
 return rows,excluded

def clusters(rows,trades,transfers,chain='solana'):
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
  cid=chain+'-C-'+hashlib.sha256('|'.join(sorted(r['wallet'] for r in members)).encode()).hexdigest()[:8]
  for r in members:r['cluster_id']=cid
  n=sum(r['matched_sell_samples'] for r in members);wins=sum(r['wins'] for r in members)
  result.append({'cluster_id':cid,'chain':chain,'members':[{'wallet':r['wallet'],'key':r['key'],'gmgn':r['gmgn'],'solscan':r['solscan'],**links(chain,r['wallet'])} for r in members],'matched_sell_samples':n,'win_rate_pct':round(wins/n*100,2) if n else None,'observed_realized_pnl_usd':round(sum(r['observed_realized_pnl_usd'] or 0 for r in members),4) if n else None,'score':round(sum((r['score'] or 0)*r['matched_sell_samples'] for r in members)/n,2) if n else None,'warning':'Heuristic link, not confirmed ownership. Summed observed member P&L may double count inter-wallet economic exposure.','evidence':[e for e in edges if e['a'] in {r['wallet'] for r in members} and e['b'] in {r['wallet'] for r in members}]})
 return sorted(result,key=lambda r:r['score'] or -1,reverse=True)

def run():
 cfg=load(ROOT/'config.json',{});priority='--solana-priority' in sys.argv;old_out=load(DATA/'wallets.json',{});profiles=load(ROOT/'agents.json',[]);q=FetchQueue();chat=[];errors=[];sources=([s for s in old_out.get('sources',[]) if s.get('chain')!='solana'] if priority else []);chain_stats=copy.deepcopy(old_out.get('chain_stats',{})) if priority else {};contexts=load(DATA/'chain-context.json',{}) if priority else {};observed=[];verification=load(DATA/'chain-verification.json',{}) if priority else {};all_base=[];bot_excluded=[]
 def say(a,m):chat.append({'agent':a,'time_et':stamp(),'text':m});print(a+': '+m,flush=True)
 say('Publisher','Starting 50 real deterministic hunting jobs across Solana, BNB and Robinhood; no Ethereum mainnet and no transactions sent.')
 previous=load(DATA/'observations.json',[])
 for t in previous:t.setdefault('chain','solana')
 known={t['id'] for t in previous};old_context=load(DATA/'chain-context.json',{})
 for chain in (['solana'] if priority else cfg['chains']):
  c=CHAINS[chain];pools=[];dex=[];current=[];liq={};transfers=[];checked=0
  try:
   query={'solana':'SOL','bsc':'0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c','robinhood':'robinhood'}[chain]
   dex=[x for x in q.get('https://api.dexscreener.com/latest/dex/search?q='+query).get('pairs',[]) if x.get('chainId')==chain]
   for pair in dex:
    if pair.get('liquidity',{}).get('usd'):liq[pair['baseToken']['address']]=num(pair['liquidity']['usd'])
  except Exception as e:errors.append(chain+' Dex discovery: '+str(e))
  try:pools=q.get(f'https://api.geckoterminal.com/api/v2/networks/{chain}/trending_pools?include=base_token,quote_token').get('data',[])[:c['pools']]
  except Exception as e:errors.append(chain+' Gecko discovery: '+str(e))
  for pool in pools:
   a=pool['attributes'];token=pool['relationships']['base_token']['data']['id'].removeprefix(chain+'_');liq[token]=num(a.get('reserve_in_usd'))
   try:
    items=q.get(f"https://api.geckoterminal.com/api/v2/networks/{chain}/pools/{a['address']}/trades").get('data',[])
    for item in items:
     t=item['attributes'];buy=t['kind']=='buy';wallet=t.get('tx_from_address');wallet=wallet.lower() if chain!='solana' and wallet else wallet
     current.append({'id':item['id'],'chain':chain,'wallet':wallet,'token':token,'kind':t['kind'],'quantity':num(t.get('to_token_amount' if buy else 'from_token_amount')),'usd':num(t.get('volume_in_usd')),'time':t['block_timestamp'],'tx':t['tx_hash'],'pool':a['address'],'anomalous':t.get('is_anomalous',False)})
   except Exception as e:errors.append(chain+' pool '+a['address']+': '+str(e))
  if chain=='solana':
   v={'chain':chain,'errors':[],'attribution_checks':[]}
   try:
    v['slot']=q.rpc(chain,'getSlot')
    for tx in list(dict.fromkeys(t['tx'] for t in current))[:cfg['rpc_transaction_limit']]:
     try:
      j=q.rpc(chain,'getTransaction',[tx,{'encoding':'jsonParsed','maxSupportedTransactionVersion':0}])
      if not j:continue
      checked+=1;v['attribution_checks'].append({'tx':tx,'signers':[k['pubkey'] for k in j['transaction']['message']['accountKeys'] if isinstance(k,dict) and k.get('signer')]})
      ins=list(j['transaction']['message'].get('instructions',[]))
      for group in j.get('meta',{}).get('innerInstructions',[]):ins+=group.get('instructions',[])
      for i in ins:
       parsed=i.get('parsed',{});info=parsed.get('info',{}) if isinstance(parsed,dict) else {}
       if i.get('program')=='system' and parsed.get('type')=='transfer' and info.get('source') and info.get('destination'):transfers.append({'from':info['source'],'to':info['destination'],'lamports':info.get('lamports'),'tx':tx})
     except Exception as e:v['errors'].append(str(e));break
   except Exception as e:v['errors'].append(str(e))
  else:
   rpc_pools=pools or [{'attributes':{'address':p['pairAddress']}} for p in dex[:1]]
   v=verify_evm(q,chain,rpc_pools,max_logs=3);checked=len(v['decoded_swaps']);transfers=v.get('native_transfers',[])
   if not current and v.get('decoded_swaps'):
    base=(pools[0]['relationships']['base_token']['data']['id'].removeprefix(chain+'_') if pools else dex[0]['baseToken']['address']).lower()
    for raw in v['decoded_swaps']:
     zero=base==v['token0'].lower();index=0 if zero else 1
     delta=(raw.get('amount'+str(index)+'_in_raw',0)-raw.get('amount'+str(index)+'_out_raw',0)) if raw['version']=='v2' else raw['amount'+str(index)+'_delta_raw']
     current.append({'id':chain+':rpc:'+raw['tx']+':'+str(raw['log_index']),'chain':chain,'wallet':raw['wallet'],'token':base,'kind':'sell' if delta>0 else 'buy','quantity':abs(delta)/(10**v['decimals'][v['token0'] if zero else v['token1']]),'usd':0,'time':raw['block_time'],'tx':raw['tx'],'pool':raw['pool'],'anomalous':False,'valuation':'historical USD unavailable; excluded from P&L and copy fills','attribution_verified':True})
   # Reconcile provider-reported trade origin against bounded independently parsed Swap logs.
   origins={x['tx']:x['wallet'] for x in v['decoded_swaps']}
   for t in current:
    if t['tx'] in origins:t['wallet']=origins[t['tx']];t['attribution_verified']=True
  verification[chain]=v;observed+=current;contexts[chain]={'liquidity':liq,'pools':[{'address':p['attributes']['address'],'token':p['relationships']['base_token']['data']['id'].removeprefix(chain+'_'),'name':p['attributes']['name'],'volume_24h_usd':p['attributes'].get('volume_usd',{}).get('h24')} for p in pools],'transfers':transfers,'updated_at_et':stamp()}
  chain_stats[chain]={'sample_updated_at_et':stamp(),'fetched_this_cycle':True,'tokens_scanned':len(liq),'pools_selected':len(pools),'priced_pool_windows':len({t['pool'] for t in current if t['usd']>0}),'swaps_this_cycle':len(current),'wallets_this_cycle':len({t['wallet'] for t in current if wallet_ok(t['wallet'])}),'dex_pairs':len(dex),'rpc_swaps_checked':checked,'verification_only':True,'status':('active sampled price feed' if any(t['usd']>0 for t in current) else 'RPC active; historical USD prices pending' if current else 'pending data source'),'rpc_errors':v.get('errors',[]),'chain_id':c['id'],'geckoterminal_network':chain,'dexscreener_chain':chain,'explorer':c['explorer'],'gmgn_supported':bool(c['gmgn'])}
  sources.append({'chain':chain,'provider':'DexScreener + GeckoTerminal + public RPC','status':chain_stats[chain]['status'],'data':'Recent sampled swaps; not full chain history'})
  say(c['name'],f"{len(liq)} tokens, {len(current)} recent swaps; {checked} bounded RPC checks; {len(v.get('errors',[]))} RPC errors.")
 all_trades=list({t['id']:t for t in previous+observed}.values());new=[t for t in observed if t['id'] not in known];save(DATA/'observations.json',all_trades);save(DATA/'chain-context.json',contexts);save(DATA/'chain-verification.json',verification)
 base_cfg=copy.deepcopy(cfg);base_cfg['features']['copy_trade_ranking']=False
 for chain in cfg['chains']:
  chain_trades=[t for t in all_trades if t.get('chain','solana')==chain]
  base,excluded=account(chain_trades,contexts[chain]['liquidity'],base_cfg,chain);all_base+=base;bot_excluded +=[{**x,'chain':chain,'key':chain+':'+x['wallet']} for x in excluded]
  chain_stats[chain]['wallets_accumulated']=len({t['wallet'] for t in chain_trades if wallet_ok(t['wallet'])})
  if not chain_stats[chain]['swaps_this_cycle'] and chain_trades:chain_stats[chain]['status']='cached swaps; current provider rate-limited/unavailable'
  chain_stats[chain]['bot_wash_excluded']=len(excluded)
 # All real hunting slices execute over the shared fetched evidence and feed the master queue.
 for r in all_base:
  if cfg['features']['copy_trade_ranking']:
   b=r['score_breakdown'];r['score_mode']='copy_trade';r['score']=round(sum((b.get(k) or 0)*v for k,v in r['copy_score_weights'].items())*b['sample_confidence'],2) if r['hold_window_pass'] and b['copy_capture_samples'] else None
 all_base.sort(key=lambda r:(r['qualified'],r['score'] if r['score'] is not None else -1),reverse=True)
 now=stamp();hunters,contributed=hunt(profiles,all_base,all_trades,{},cfg,now)
 eligible=[r for r in all_base if (r['hold_window_pass'] and r['mean_liquidity_usd']>=cfg['minimum_liquidity_usd'] and r['key'] in contributed)] if cfg['features']['copy_trade_ranking'] else all_base
 simulations={r['key']:simulate(r,all_trades,cfg,now) for r in eligible}
 for r in eligible:r['copy_simulation']=simulations[r['key']];r['standout']=r['copy_simulation']['standout'];r['hunter_ids']=[h['id'] for h in hunters if r['key'] in h['candidate_keys']]
 hunters,contributed=hunt(profiles,all_base,all_trades,simulations,cfg,now)
 grouped=[]
 for chain in cfg['chains']:
  cr=[r for r in eligible if r['chain']==chain];cts=[t for t in all_trades if t.get('chain','solana')==chain]
  if cfg['features']['cluster_detection']:grouped+=clusters(cr,cts,contexts[chain]['transfers'],chain)
  chain_stats[chain].update({'hold_window_pass':sum(r['hold_window_pass'] for r in all_base if r['chain']==chain),'liquidity_pass':sum(r['mean_liquidity_usd']>=cfg['minimum_liquidity_usd'] for r in all_base if r['chain']==chain),'both_pass':len(cr),'min_sell_sample_pass':sum(r['matched_sell_samples']>=cfg['minimum_closed_samples'] for r in cr),'min_months_pass':sum(r['observed_months']>=cfg['minimum_observed_months'] for r in cr),'qualified':sum(r['qualified'] for r in cr),'clusters':sum(c['chain']==chain for c in grouped),'hunters_executed':sum(h['chain']==chain for h in hunters)})
 learning=build_learning(simulations,load(DATA/'lessons.json',{}),cfg,now);save(DATA/'lessons.json',learning)
 for h in hunters:say(h['name'],f"{h['chain']} slice completed: {h['wallets_evaluated']} wallets evaluated, {h['candidate_count']} match; best="+(h['best_wallet']['wallet'] if h['best_wallet'] else 'insufficient data'))
 for review in learning['reviews'][-10:]:chat.append({'agent':'Loss Review Council','time_et':review['time_et'],'text':review['text'],'evidence':review['evidence']})
 alerts=load(DATA/'alerts.json',[]);alert_ids={a['id'] for a in alerts};top={r['key'] for r in eligible[:10]}
 if cfg['features']['new_buy_alert_feed']:
  for t in (new if previous else []):
   if t['kind']=='buy' and t['chain']+':'+str(t['wallet']) in top and t['id'] not in alert_ids:alerts.append({'id':t['id'],'chain':t['chain'],'wallet':t['wallet'],'token':t['token'],'observed_at_et':now,'block_time':t['time'],'usd':t['usd'],'solscan':CHAINS[t['chain']]['tx_explorer']+t['tx'],'text':'Newly observed sampled buy; site-only, not real-time.'});alert_ids.add(t['id'])
 save(DATA/'alerts.json',alerts[-200:]);save(DATA/'copy-simulations.json',{'updated_at_et':now,'accounts':simulations});save(DATA/'hunting-results.json',hunters)
 goal={'status':'active','date_et':dt.datetime.now(ET).strftime('%Y-%m-%d'),'goal_usd':cfg['daily_profit_goal_usd'],'starting_balance_per_account_usd':cfg['copy_sim_starting_balance_usd'],'required_daily_return_pct':cfg['daily_profit_goal_usd']/cfg['copy_sim_starting_balance_usd']*100,'accounts':[{ 'wallet_key':k,'realized_today_usd':v['today_realized_pnl_usd'],'goal_hit':v['goal_hit'],'standout':v['standout']} for k,v in simulations.items()],'standout_wallets':[k for k,v in simulations.items() if v['standout']],'note':'Per-account goal, not sum of hypothetical independent accounts. Closed paper fills only; ET-day entry-stop latch survives deterministic replay, open positions still managed.'};save(DATA/'daily-goals.json',goal)
 excluded=bot_excluded+[{'wallet':r['wallet'],'chain':r['chain'],'key':r['key'],'reasons':(['copy hold window outside 1h–1week or unknown'] if not r['hold_window_pass'] else [])+(['liquidity below floor or not in current pool sample'] if r['mean_liquidity_usd']<cfg['minimum_liquidity_usd'] else [])} for r in all_base if r not in eligible]
 if priority:
  for other in ['bsc','robinhood']:
   chain_stats[other]['fetched_this_cycle']=False;chain_stats[other]['sample_updated_at_et']=chain_stats[other].get('sample_updated_at_et',old_out.get('updated_at_et'));chain_stats[other]['status']='cached; unchanged during Solana-priority scan'
 stats={'dex_pairs_scanned':sum(x['dex_pairs'] for x in chain_stats.values()),'tokens_scanned':sum(x['tokens_scanned'] for x in chain_stats.values()),'swaps_this_cycle':len(observed),'new_swaps':len(new),'wallets_scanned':sum(x['wallets_accumulated'] for x in chain_stats.values()),'wallets_published':len(eligible),'qualified_wallets':sum(r['qualified'] for r in eligible),'qualified_copy_wallets':sum(r['qualified'] for r in eligible),'hold_window_survivors':len(eligible),'hold_window_pass_alone':sum(r['hold_window_pass'] for r in all_base),'liquidity_pass_alone':sum(r['mean_liquidity_usd']>=cfg['minimum_liquidity_usd'] for r in all_base),'bot_wash_exclusions':len(bot_excluded),'minimum_sell_sample_pass':sum(r['matched_sell_samples']>=cfg['minimum_closed_samples'] for r in eligible),'minimum_months_pass':sum(r['observed_months']>=cfg['minimum_observed_months'] for r in eligible),'excluded_wallets':len(excluded),'hunters_executed':len(hunters),'hunters_with_candidates':sum(h['candidate_count']>0 for h in hunters),'simulated_closed_fills':sum(v['closed_trades'] for v in simulations.values()),'simulated_open_positions':sum(v['open_positions'] for v in simulations.values()),'clusters_found':len(grouped)}
 out={'updated_at':iso(),'updated_at_et':now,'scan_mode':'solana-priority' if priority else 'all-chains-solana-first','schedule':'ON: one local hourly research publisher' if cfg.get('hourly_enabled') else 'OFF','features':cfg['features'],'feature_status':{k:('enabled_sampled_evidence' if v else 'off') for k,v in cfg['features'].items()},'thresholds':{k:v for k,v in cfg.items() if k!='features'},'agents':hunters,'stats':stats,'chain_stats':chain_stats,'chains':[{**c,'key':k,'status':chain_stats[k]['status']} for k,c in CHAINS.items()],'sources':sources,'errors':errors,'fetch_queue':q.summary(),'limits':['All 50 named hunters execute distinct chain/liquidity/hold slices over one serial cached fetch queue. They are deterministic research workers, not 50 LLM models.','Recent trending-pool swaps are sampled and incomplete; no full wallet, full-chain or multi-month history is established. RPC origin checks are bounded.','Source-wallet FIFO P&L is observed matched quantities before fees, transfers and missing inventory. It is not total-account P&L.','Copy replay uses chronological observed prices: 60s entry delay, first net +35% sampled exit or source sell/one-week timeout, finite $500 balance, modeled each-side fees and slippage. Sparse ticks and retrospective wallet selection introduce bias.','Copy-capture rates use best sampled opportunities and are not the paper replay return. Expected daily profit and capital required remain insufficient data. $300/day from $500 requires 60% per day; no evidence supports it here.','Historical entry market cap, true peak, executable depth and complete price paths are unknown. 3x means +200%. No claim of insider status or guaranteed copying profit.','Clusters are within each chain only. No unproven cross-chain ownership linkage is made. RPC funding samples and timing heuristics are incomplete.','Robinhood mainnet verified from official docs and RPC chainId 4663; provider network id robinhood. GMGN Robinhood support is unverified, so only the official explorer is linked. No Ethereum-mainnet data is requested.','Learning is evidence-backed simulated-loss review and suggestion-only. It never auto-changes thresholds. All charts show actual observed/replayed data, not synthetic historical returns.','Public API rate limits and hourly polling miss activity. Modeled fees differ from actual tax/gas/depth. Free sampled data cannot establish expected returns or the capital needed for $300/day.'],'wallets':eligible,'clusters':grouped,'excluded':excluded,'agent_chat':chat,'alerts':alerts[-100:] if cfg['features']['new_buy_alert_feed'] else [],'learning':learning,'daily_goal':goal,'copy_simulation':{'enabled':cfg['features']['copy_account_simulation'],'status':'active_sampled_replay','starting_balance_usd':cfg['copy_sim_starting_balance_usd'],'expected_profit_per_day_usd':None,'capital_needed_for_300_per_day_usd':None,'reason':'Insufficient complete historical coverage; simulations are not a profit forecast.'},'observed_window':{'first_trade':min((t['time'] for t in all_trades),default=None),'last_trade':max((t['time'] for t in all_trades),default=None)}}
 save(DATA/'wallets.json',out);save(DATA/'agent-chat.json',chat)
 from agent_accounts import attach
 out=attach(out,ROOT)
 from solana_view import attach as attach_solana_view
 out=attach_solana_view(out,ROOT)
 print(json.dumps(out['stats']),flush=True)
if __name__=='__main__':run()
