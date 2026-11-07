"""Shared public-read queue, multi-chain evidence, 50 deterministic hunters, paper replay."""
import collections,datetime as dt,hashlib,json,math,time
import requests
from zoneinfo import ZoneInfo
ET=ZoneInfo('America/New_York')
CHAINS={
 'solana':{'name':'Solana','id':None,'rpc':'https://api.mainnet-beta.solana.com','explorer':'https://solscan.io/account/','tx_explorer':'https://solscan.io/tx/','gmgn':'https://gmgn.ai/sol/address/','pools':2},
 'bsc':{'name':'BNB Chain','id':56,'rpc':'https://bsc-rpc.publicnode.com','explorer':'https://bscscan.com/address/','tx_explorer':'https://bscscan.com/tx/','gmgn':'https://gmgn.ai/bsc/address/','pools':2},
 'robinhood':{'name':'Robinhood Chain','id':4663,'rpc':'https://rpc.mainnet.chain.robinhood.com','explorer':'https://robinhoodchain.blockscout.com/address/','tx_explorer':'https://robinhoodchain.blockscout.com/tx/','gmgn':None,'pools':2}
}
def when(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def et(s):return when(s).astimezone(ET).strftime('%Y-%m-%d %I:%M:%S %p ET')
def day(s):return when(s).astimezone(ET).strftime('%Y-%m-%d')
def links(chain,w):
 c=CHAINS[chain];return {'explorer':c['explorer']+w,'explorer_name':'Solscan' if chain=='solana' else 'BscScan' if chain=='bsc' else 'Robinhood Explorer','gmgn':c['gmgn']+w if c['gmgn'] else None}
class FetchQueue:
 """All hunters share this serial queue; cache identical requests, honor provider limits."""
 def __init__(self):self.cache={};self.last={};self.count=0;self.hits=0;self.failures=[];self.session=requests.Session();self.suspended=set()
 def request(self,url,payload=None):
  key=url+json.dumps(payload,sort_keys=True)
  if key in self.cache:self.hits+=1;return self.cache[key]
  host=url.split('/')[2]
  if host in self.suspended:raise RuntimeError(host+' suspended after rate limit; no bypass/retry this cycle')
  interval=13.0 if 'geckoterminal' in host else 5.1 if host=='api.mainnet-beta.solana.com' else 1.1 if payload else .3
  time.sleep(max(0,interval-(time.monotonic()-self.last.get(host,0))))
  self.last[host]=time.monotonic();self.count+=1
  try:
   r=self.session.post(url,json=payload,timeout=22) if payload else self.session.get(url,timeout=22,headers={'User-Agent':'WalletHunters/2.0 public read-only research'})
   if r.status_code==429:self.suspended.add(host)
   r.raise_for_status();j=r.json()
   if isinstance(j,dict) and 'error' in j:raise RuntimeError(str(j['error']))
   self.cache[key]=j;return j
  except Exception as e:
   self.failures.append({'host':host,'error':str(e)});print('SOURCE ERROR '+host+': '+str(e),flush=True);raise
 def get(self,url):return self.request(url)
 def rpc(self,chain,method,params=[]):return self.request(CHAINS[chain]['rpc'],{'jsonrpc':'2.0','id':1,'method':method,'params':params}).get('result')
 def summary(self):return {'requests':self.count,'cache_hits':self.hits,'failures':self.failures,'model':'One serial cached queue shared by all 50 hunters; GT 13s, Solana RPC 5.1s, EVM RPC 1.1s minimum spacing; stop host on HTTP 429.'}

def hash_topic(signature):
 from Crypto.Hash import keccak
 h=keccak.new(digest_bits=256);h.update(signature.encode());return '0x'+h.hexdigest()
V2_SIG='Swap(address,uint256,uint256,uint256,uint256,address)'
V3_SIG='Swap(address,address,int256,int256,uint160,uint128,int24)'
def decode_swap(log):
 """Decode standard V2/V3 raw amounts only. Never treat indexed router/recipient as owner."""
 topic=log['topics'][0].lower();raw=log['data'].removeprefix('0x')
 if len(raw)%64:raise ValueError('Malformed ABI words')
 words=[int(raw[i:i+64],16) for i in range(0,len(raw),64)]
 if topic==hash_topic(V2_SIG):
  if len(words)!=4:raise ValueError('V2 Swap requires four non-indexed uint256 amounts')
  return {'version':'v2','amount0_in_raw':words[0],'amount1_in_raw':words[1],'amount0_out_raw':words[2],'amount1_out_raw':words[3]}
 if topic==hash_topic(V3_SIG):
  if len(words)<5:raise ValueError('V3 Swap requires signed amounts and price/liquidity/tick')
  signed=lambda x:x-2**256 if x>=2**255 else x
  return {'version':'v3','amount0_delta_raw':signed(words[0]),'amount1_delta_raw':signed(words[1]),'sqrt_price_x96':words[2],'liquidity_raw':words[3],'tick':signed(words[4])}
 raise ValueError('Unsupported Swap event; do not guess')

def verify_evm(queue,chain,pools,max_logs=4):
 """Bounded eth_getLogs with correct ABI and tx-origin attribution. Raw evidence, not invented USD P&L."""
 out={'chain':chain,'expected_chain_id':CHAINS[chain]['id'],'verified_chain_id':None,'decoded_swaps':[],'native_transfers':[],'errors':[],'block_window':2000}
 try:
  cid=int(queue.rpc(chain,'eth_chainId'),16);out['verified_chain_id']=cid
  if cid!=CHAINS[chain]['id']:raise ValueError('Wrong network; reject RPC response')
  block=int(queue.rpc(chain,'eth_blockNumber'),16);out['latest_block']=block
  if not pools:return out
  topics=[hash_topic(V2_SIG),hash_topic(V3_SIG)]
  address=pools[0]['attributes']['address'];logs=queue.rpc(chain,'eth_getLogs',[{'address':address,'fromBlock':hex(max(0,block-2000)),'toBlock':hex(block),'topics':[topics]}]) or []
  # Read token ordering rather than assuming base=token0; decimals are ERC20 ABI calls.
  token0='0x'+queue.rpc(chain,'eth_call',[{'to':address,'data':'0x0dfe1681'},'latest'])[-40:]
  token1='0x'+queue.rpc(chain,'eth_call',[{'to':address,'data':'0xd21220a7'},'latest'])[-40:]
  decimals={tok:int(queue.rpc(chain,'eth_call',[{'to':tok,'data':'0x313ce567'},'latest']),16) for tok in [token0,token1]}
  out.update({'pool':address,'token0':token0,'token1':token1,'decimals':decimals,'logs_found':len(logs)})
  for log in logs[-max_logs:]:
   try:
    decoded=decode_swap(log);tx=queue.rpc(chain,'eth_getTransactionByHash',[log['transactionHash']])
    if not tx:continue
    receipt=queue.rpc(chain,'eth_getTransactionReceipt',[log['transactionHash']])
    if not receipt or int(receipt.get('status','0x0'),16)!=1:continue
    fullblock=queue.rpc(chain,'eth_getBlockByNumber',[log['blockNumber'],True])
    for native in fullblock.get('transactions',[]):
     if isinstance(native,dict) and native.get('to') and int(native.get('value','0x0'),16)>0:
      edge={'from':native['from'].lower(),'to':native['to'].lower(),'wei':int(native['value'],16),'tx':native['hash']}
      if edge not in out['native_transfers']:out['native_transfers'].append(edge)
    rawgas=int(receipt.get('gasUsed','0x0'),16)*int(receipt.get('effectiveGasPrice',tx.get('gasPrice','0x0')),16)
    # ETH/WBNB native fee remains native: no invented historical USD conversion.
    out['decoded_swaps'].append({**decoded,'pool':address,'tx':log['transactionHash'],'block_number':int(log['blockNumber'],16),'log_index':int(log['logIndex'],16),'wallet':tx['from'].lower(),'attribution':'transaction origin, not router/event recipient; smart-account attribution may still differ','block_time':dt.datetime.fromtimestamp(int(queue.rpc(chain,'eth_getBlockByNumber',[log['blockNumber'],False])['timestamp'],16),dt.timezone.utc).isoformat(),'gas_fee_native':rawgas/1e18,'usd_valuation':'Use provider timestamped swap prices separately; raw logs are not USD-priced P&L','explorer':CHAINS[chain]['tx_explorer']+log['transactionHash']})
   except Exception as e:out['errors'].append(str(e))
 except Exception as e:out['errors'].append(str(e))
 return out

def hunt(profiles,rows,all_trades,simulations,cfg,now):
 """Every profile executes its distinct chain/liquidity/hold slice and contributes candidates."""
 output=[];contributed=set()
 for profile in profiles:
  s=profile['slice'];scanned=[r for r in rows if r['chain']==profile['chain']]
  candidates=[r for r in scanned if s['liquidity_min_usd']<=r['mean_liquidity_usd']<s['liquidity_max_usd'] and r['average_hold_seconds'] is not None and s['hold_min_seconds']<=r['average_hold_seconds']<=s['hold_max_seconds'] and r['matched_sell_samples']>=s['min_matched_sells']]
  def specialized(r):
   b=r['score_breakdown'];weights=s['weights'];return sum((b.get(k) or 0)*v for k,v in weights.items())*(b.get('sample_confidence') or 0)
  candidates.sort(key=lambda r:(specialized(r),r['score'] or -1),reverse=True)
  best=candidates[0] if candidates else None
  for r in candidates:contributed.add(r['key'])
  summary={k:best[k] for k in ['key','wallet','chain','score','win_rate_pct','observed_realized_pnl_usd','gmgn','explorer','explorer_name']} if best else None
  sim=simulations.get(best['key'],empty_account(cfg,now,'No replay account yet; insufficient observations.')) if best else empty_account(cfg,now,'No candidate in this agent’s real slice.')
  output.append({**profile,'clocked_in':True,'last_run_et':now,'wallets_evaluated':len(scanned),'candidate_count':len(candidates),'candidate_keys':[r['key'] for r in candidates],'best_wallet':summary,'slice_score':round(specialized(best),4) if best else None,'status':'completed' if best else 'completed_no_match','copy_simulation':{**sim,'account_id':profile['id'],'copied_wallet':best['key'] if best else None},'role':profile['job']})
 return output,contributed

def empty_account(cfg,now,reason='No eligible observations.'):
 return {'enabled':cfg['features'].get('copy_account_simulation',False),'status':'insufficient_data','starting_balance_usd':cfg['copy_sim_starting_balance_usd'],'balance_usd':cfg['copy_sim_starting_balance_usd'],'equity_usd':cfg['copy_sim_starting_balance_usd'],'trades':0,'closed_trades':0,'open_positions':0,'realized_pnl_usd':0,'today_realized_pnl_usd':0,'daily_history':[],'monthly_history':[],'equity_history':[],'expected_profit_per_day_usd':None,'capital_needed_for_300_per_day_usd':None,'sampled_profit_per_day_usd':None,'goal_hit':False,'standout':False,'fills':[],'reason':reason,'as_of_et':now}

def simulate(wallet_row,market,cfg,now,entry_start_at=None):
 """Chronological observed-tick replay: delayed entries, first target/source sell exits, finite cash, fees.
 No future peak used to execute a fill; selection of the wallet remains retrospective and biased.
 """
 result=empty_account(cfg,now);chain=wallet_row['chain'];wallet=wallet_row['wallet'];c=cfg['simulation'];start=cfg['copy_sim_starting_balance_usd']
 if not result['enabled']:return result
 eligible_tokens={t['token'] for t in market if t['wallet']==wallet and t.get('chain','solana')==chain}
 ticks=sorted([t for t in market if (entry_start_at is None or when(t['time'])>=when(entry_start_at)) and t.get('chain','solana')==chain and t['token'] in eligible_tokens and t['quantity']>0 and t['usd']>0],key=lambda t:(t['time'],t['id']))
 if not ticks:return result
 cash=start;positions=[];pending=[];fills=[];daily=collections.defaultdict(float);stopped=set();equity=[];last={};seen=set();skipped=collections.Counter()
 fee_rate=c['fee_bps_per_side'][chain]/10000;network=c['network_fee_usd_per_side'][chain];liquidity=wallet_row['mean_liquidity_usd'];slip=cfg['copy_slippage_pct']/100+min(.5,cfg['copy_order_usd']/max(1,liquidity))
 for tick in ticks:
  ts=when(tick['time']);px=tick['usd']/tick['quantity'];last[tick['token']]=px;current_day=day(tick['time'])
  # Manage every open position even after a daily entry stop has latched.
  for pos in list(positions):
   if pos['token']!=tick['token'] or ts<=pos['entry_dt']:continue
   proceeds=pos['quantity']*px*(1-slip)*(1-fee_rate)-network
   net=max(0,proceeds)-pos['cost'];netpct=net/pos['cost']*100
   reason='target_35' if netpct>=c['take_profit_pct'] else 'source_sell' if tick['wallet']==wallet and tick['kind']=='sell' else 'max_hold' if (ts-pos['entry_dt']).total_seconds()>=cfg['max_avg_hold_seconds'] else None
   if not reason:continue
   cash+=max(0,proceeds);positions.remove(pos);daily[current_day]+=net
   if daily[current_day]>=cfg['daily_profit_goal_usd']:stopped.add(current_day)
   fid=hashlib.sha256((wallet_row['key']+pos['source_id']+tick['id']).encode()).hexdigest()[:20]
   fills.append({'id':fid,'wallet_key':wallet_row['key'],'chain':chain,'token':pos['token'],'source_buy':pos['source_id'],'exit_observation':tick['id'],'entry_time':pos['entry_dt'].isoformat(),'exit_time':tick['time'],'entry_time_et':et(pos['entry_dt'].isoformat()),'exit_time_et':et(tick['time']),'cost_usd':round(pos['cost'],6),'proceeds_usd':round(max(0,proceeds),6),'pnl_usd':round(net,6),'return_pct':round(netpct,4),'reason':reason,'fees_usd':round(pos['entry_fee']+pos['quantity']*px*(1-slip)*fee_rate+network,6),'slippage_pct_per_side':round(slip*100,6),'source_tx':tick['tx'],'source_explorer':CHAINS[chain]['tx_explorer']+tick['tx']})
  if tick['wallet']==wallet and tick['kind']=='sell':pending=[p for p in pending if p['token']!=tick['token']]
  for signal in list(pending):
   if ts>signal['expires']:pending.remove(signal);skipped['entry_price_missing']+=1;continue
   if signal['token']!=tick['token'] or ts<signal['ready']:continue
   pending.remove(signal)
   if current_day in stopped:skipped['daily_stop']+=1;continue
   if len(positions)>=c['max_open_positions']:skipped['position_cap']+=1;continue
   cost=min(cfg['copy_order_usd'],cash)
   if cost<c['minimum_order_usd'] or cost<=network:skipped['cash_limit']+=1;continue
   entry_fee=cost*fee_rate+network;invested=max(0,cost-entry_fee);quantity=invested/(px*(1+slip));cash-=cost
   positions.append({'source_id':signal['source_id'],'token':tick['token'],'entry_dt':ts,'cost':cost,'quantity':quantity,'entry_fee':entry_fee})
  if tick['wallet']==wallet and tick['kind']=='buy' and tick['id'] not in seen:
   seen.add(tick['id']);ready=ts+dt.timedelta(seconds=cfg['copy_delay_seconds']);pending.append({'source_id':tick['id'],'token':tick['token'],'ready':ready,'expires':ready+dt.timedelta(seconds=cfg['copy_entry_max_gap_seconds'])})
  marked=cash+sum(max(0,p['quantity']*last.get(p['token'],0)*(1-slip)*(1-fee_rate)-network) for p in positions)
  if not equity or tick['time'][:16]!=equity[-1]['time'][:16]:equity.append({'time':tick['time'],'equity_usd':round(marked,4)})
 today=dt.datetime.now(ET).strftime('%Y-%m-%d');realized=sum(f['pnl_usd'] for f in fills);span=(when(ticks[-1]['time'])-when(ticks[0]['time'])).total_seconds()/86400;months=collections.defaultdict(float)
 for d,pnl in daily.items():months[d[:7]]+=pnl
 result.update({'status':'replayed_sample_insufficient_for_forecast','balance_usd':round(cash,4),'equity_usd':round(cash+sum(max(0,p['quantity']*last.get(p['token'],0)*(1-slip)*(1-fee_rate)-network) for p in positions),4),'trades':len(fills)+len(positions),'closed_trades':len(fills),'open_positions':len(positions),'realized_pnl_usd':round(realized,6),'today_realized_pnl_usd':round(daily.get(today,0),6),'daily_history':[{'date_et':d,'pnl_usd':round(p,6),'partial':True} for d,p in sorted(daily.items())],'monthly_history':[{'month':m,'pnl_usd':round(p,6),'partial':True} for m,p in sorted(months.items())],'equity_history':equity[-500:],'sampled_profit_per_day_usd':round(realized/span,4) if span>=1 else None,'sample_days':round(span,4),'goal_hit':today in stopped,'goal_stop_days':sorted(stopped),'fills':fills,'skipped':dict(skipped),'reason':'Retrospective wallet selection, sparse historical ticks, partial coverage. Expected daily profit and capital needed remain insufficient data, not a forecast. Modeled fees/slippage, not measured execution costs.','assumptions':{'fee_bps_per_side':c['fee_bps_per_side'][chain],'network_fee_usd_per_side':network,'delay_seconds':cfg['copy_delay_seconds'],'slippage_pct_per_side':cfg['copy_slippage_pct'],'take_profit_pct':c['take_profit_pct'],'cash_allocation_per_entry':cfg['copy_order_usd'],'source_sell_exit':'Exit entire copied token position at first observed source sell. No stop-loss.','historical_liquidity':'Current pool liquidity used as proxy; no executable historical depth.'}})
 # Standout is earned only by real simulated closed fills today meeting goal AND the evidence floor.
 result['standout']=bool(cfg['features'].get('standout_badges') and wallet_row['qualified'] and result['today_realized_pnl_usd']>=cfg['daily_profit_goal_usd'])
 return result

def build_learning(simulations,old,cfg,now):
 lessons={x['id']:x for x in old.get('lessons',[])};reviews={x['id']:x for x in old.get('reviews',[])}
 if cfg['features'].get('agent_learning'):
  for key,sim in simulations.items():
   for f in sim['fills']:
    if f['pnl_usd']>=0 or f['id'] in reviews:continue
    reviews[f['id']]={'id':f['id'],'wallet_key':key,'time_et':f['exit_time_et'],'generated_at_et':now,'kind':'simulated_loss_review','pnl_usd':f['pnl_usd'],'fees_usd':f['fees_usd'],'text':f"Modeled copy loss ${abs(f['pnl_usd']):.4f}; exit={f['reason']}. The delayed, slipped entry plus modeled fees did not recover before this observed exit. This is a simulation result, not a proven reason for the source trader’s decision.",'evidence':f['source_explorer']}
    lid='fee-and-delay' if abs(f['pnl_usd'])<=f['fees_usd']*2 else 'source-exit-risk'
    lesson=lessons.setdefault(lid,{'id':lid,'text':'Before promoting a wallet, stress-test delay, fee drag and sparse price coverage.' if lid=='fee-and-delay' else 'Observed source exits can precede the follower’s target. Validate exit risk out of sample before copying.','status':'suggestion_only','automatically_applied':False,'evidence_fill_ids':[]})
    if f['id'] not in lesson['evidence_fill_ids']:lesson['evidence_fill_ids'].append(f['id'])
 return {'status':'active','updated_at_et':now,'lessons':list(lessons.values()),'reviews':list(reviews.values())[-200:],'note':'Evidence-backed simulated-loss reviews only. Suggestions never change strategy or flags automatically.'}
