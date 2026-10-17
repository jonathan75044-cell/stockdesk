// Read-only discovery list; never promotes a candidate into trade eligibility.
const zonePanel=document.createElement('section');zonePanel.className='panel card';
zonePanel.innerHTML='<h2>Swing pullback watchlist · days to weeks</h2><p>Discovery: 38.2%–61.8% · Priority golden zone: 50%–61.8%. Dated recent daily swing anchors, not 52-week extremes. Independent of fundamental eligibility; membership is not an entry signal.</p><label><input id="golden-only" type="checkbox" checked> Show priority 50%–61.8% only</label><p id="zone-status"></p><p>Optional hypothetical sizing: <label>Cash budget ($) <input id="plan-cash" type="number" min="0" step="any" placeholder="Enter budget"></label> <label>Maximum planned loss ($) <input id="plan-risk" type="number" min="0" step="any" placeholder="Enter risk limit"></label></p><div class="tablewrap"><table><thead><tr><th>Stock</th><th>Price</th><th>Retracement</th><th>50%–61.8% band</th><th>Anchor dates</th><th>Evidence / status</th><th>Entry plan / chart</th></tr></thead><tbody id="zone-rows"></tbody></table></div>';
document.querySelector('#desk .reports').before(zonePanel);
function renderZones(){
 renderMarketContext();renderWatchlistResearch();
 const rows=(state.golden_zones||[]).filter(r=>!document.getElementById('golden-only').checked||r.priority).sort((a,b)=>Number(b.priority)-Number(a.priority)||a.symbol.localeCompare(b.symbol));
 document.getElementById('zone-status').textContent=(state.stale?'STALE / INCOMPLETE — ':'')+rows.length+' zone candidates. Conditional plans are research only; pending checks must pass before entry.';
 const body=document.getElementById('zone-rows');body.replaceChildren();
 for(const r of rows){const tr=document.createElement('tr');const quoteFresh=Date.now()-Date.parse(r.quote_at)>=0&&Date.now()-Date.parse(r.quote_at)<=900000;
 const qualified=state.rows.find(x=>x.symbol===r.symbol&&x.swing);
 for(const value of [r.symbol,money(r.price),(100*r.retracement).toFixed(1)+'%',money(r.zone_low)+' – '+money(r.priority_high),r.low_date+' → '+r.high_date,
 (state.research_only?'Closing data research · live checks pending':state.stale||!quoteFresh?'Fresh review required':qualified?'Meets trade checks':r.swing_stage||'In zone · awaiting confirmation')+' · '+(r.swing_blockers||[]).join('; ')+' · '+r.source+' · quote '+r.quote_at]){const td=document.createElement('td');td.textContent=value;tr.append(td)}
 const actions=document.createElement('td');
 const chart=document.createElement('a');chart.href=tradingViewLink(r.symbol);chart.target='_blank';chart.rel='noopener noreferrer';chart.textContent='View in TradingView';actions.append(chart);
 const button=document.createElement('button');button.type='button';button.textContent=openPlans.has(r.symbol)?'Hide entry plan':'View entry plan';button.setAttribute('aria-expanded',String(openPlans.has(r.symbol)));button.onclick=()=>{if(openPlans.has(r.symbol))openPlans.delete(r.symbol);else openPlans.add(r.symbol);renderZones()};
 actions.append(document.createElement('br'),button);tr.append(actions);tr.title=r.method;body.append(tr);
 if(openPlans.has(r.symbol)){const expanded=document.createElement('tr');const cell=document.createElement('td');cell.colSpan=7;cell.style.whiteSpace='normal';cell.innerHTML=entryPlanMarkup(r);expanded.append(cell);body.append(expanded)}
 }

}
const renderBeforeZones=renderRows;renderRows=function(){renderBeforeZones();renderZones()};
document.getElementById('golden-only').onchange=renderZones;

const openPlans=new Set();
function tradingViewLink(symbol){return 'https://www.tradingview.com/chart/?symbol='+encodeURIComponent(symbol)}
function hypotheticalPlanSize(plan,cash,riskBudget){
 if(!Number.isFinite(cash)||!Number.isFinite(riskBudget)||cash<=0||riskBudget<=0||!Number.isFinite(plan.entry)||plan.entry<=0||!Number.isFinite(plan.risk_per_share)||plan.risk_per_share<=0)return null;
 const shares=Math.floor(Math.min(cash/plan.entry,riskBudget/plan.risk_per_share));
 return {shares,cost:shares*plan.entry,plannedRisk:shares*plan.risk_per_share};
}
function entryPlanMarkup(row){
 const p=row.entry_plan;
 if(!p)return '<p>No saved entry plan. Run a fresh scan after deployment to generate one.</p>';
 const cash=Number(document.getElementById('plan-cash').value),risk=Number(document.getElementById('plan-risk').value);
 const size=hypotheticalPlanSize(p,cash,risk);
 const freshQuote=Date.now()-Date.parse(row.quote_at)>=0&&Date.now()-Date.parse(row.quote_at)<=900000;
 const status=state.stale?'STALE — refresh before using these levels':state.research_only?'After-hours research — live checks pending':!freshQuote?'Quote expired — refresh before using these levels':'Conditional plan — verify all checks';
 const values=[['Planning entry (not an order)',money(p.entry)],['Stop reference',p.stop==null?'Unavailable':money(p.stop)],['First historical target',p.target1==null?'Unavailable':money(p.target1)],['Second historical target',p.target2==null?'Unavailable':money(p.target2)],['Risk per share',p.risk_per_share==null?'Unavailable':money(p.risk_per_share)],['First-target reward / risk',p.reward_risk==null?'Unavailable':p.reward_risk.toFixed(2)+':1 (minimum '+p.minimum_rr+':1)'],['Entry ceiling for minimum reward / risk',p.max_entry_for_rr==null?'Unavailable':money(p.max_entry_for_rr)],['Average daily volume',Number(p.average_volume).toLocaleString()+' / minimum '+Number(p.minimum_average_volume).toLocaleString()],['Relative volume',p.relative_volume+'× / minimum '+p.minimum_relative_volume+'×'],['Financial checks',p.financial_status],['Earnings check',p.earnings_status]];
 return '<h3>'+esc(row.symbol)+' · conditional entry plan</h3><p><strong>'+esc(status)+'</strong></p><p>Daily bars through '+esc(p.data_date)+'. Plan is not a qualification or buy signal.</p><p>'+esc(p.trigger)+'</p>'+resistanceMarkup(p)+marketPlanMarkup(p)+'<dl>'+values.map(([label,value])=>'<dt>'+esc(label)+'</dt><dd>'+esc(value)+'</dd>').join('')+'</dl><ul>'+p.checks.map(check=>'<li>'+esc((check.passed?'Pass: ':'Pending / failed: ')+check.name)+'</li>').join('')+'</ul><p>Valuation: '+esc(watchlistValuation(row))+'</p><p>'+esc((row.swing_blockers||[]).join('; '))+'</p><p>'+esc(p.invalidation)+'</p><p>'+esc(p.method)+'</p><p>'+(size?'Hypothetical size: '+size.shares+' shares · cost '+money(size.cost)+' · planned stop loss '+money(size.plannedRisk)+'. Fees and gaps are excluded; actual loss can exceed this amount.':'Enter your cash budget and maximum planned loss above to calculate hypothetical shares.')+'</p><p><a target="_blank" rel="noopener noreferrer" href="'+esc(tradingViewLink(row.symbol))+'">View in TradingView</a> · Confirm the ticker and exchange on the chart.</p>';
}
document.getElementById('plan-cash').oninput=renderZones;
document.getElementById('plan-risk').oninput=renderZones;

const marketPanel=document.createElement('section');marketPanel.className='panel card';
zonePanel.before(marketPanel);
function marketCaution(){
 const m=state.market_context||{};
 if(state.stale)return 'Market context needs a fresh scan.';
 if(!m.SPY?.available||!m.QQQ?.available)return 'Market context is incomplete. Review benchmark charts.';
 if([m.SPY,m.QQQ].some(x=>x.freshness==='Latest completed session missing'))return 'Latest completed benchmark session is missing. Refresh before reviewing a plan.';
 if([m.SPY,m.QQQ].every(x=>x.close<x.ma50))return 'Caution: both benchmarks closed below their 50-day averages.';
 if([m.SPY,m.QQQ].every(x=>x.trend==='Uptrend'))return 'Both benchmarks meet the displayed uptrend rule. This does not confirm an individual entry.';
 return 'Mixed or weakening market context: review the benchmark charts before considering an entry.';
}
function renderMarketContext(){
 const m=state.market_context||{};
 marketPanel.innerHTML='<h2>Market context · SPY &amp; QQQ</h2><p>Completed daily closes, refreshed with each scan. Informational only; screening rules are unchanged.</p><p><strong>'+esc(marketCaution())+'</strong></p>'+['SPY','QQQ'].map(symbol=>{
 const b=m[symbol];
 return '<h3>'+symbol+'</h3><p>'+(b?.available?esc(b.trend)+' · Close '+money(b.close)+' · 20-day average '+money(b.ma20)+' · 50-day average '+money(b.ma50)+' · Through '+esc(b.data_date)+' · '+esc(b.freshness):esc(b?.reason||'Run a fresh scan to load benchmark context.'))+'</p><p><a target="_blank" rel="noopener noreferrer" href="'+tradingViewLink(symbol)+'">View '+symbol+' in TradingView</a></p>';
 }).join('')+'<p>Uptrend: close &gt; 20-day average &gt; 50-day average. Downtrend: close &lt; 20-day average &lt; 50-day average. Otherwise: Mixed. Closing data is not a live quote.</p>';
}
function marketPlanMarkup(plan){
 return '<h4>Market context and relative strength</h4><p>'+esc(marketCaution())+'</p>'+['SPY','QQQ'].map(symbol=>{
 const r=plan.relative_strength?.[symbol];
 return '<p>'+symbol+': '+(r?.available?'stock '+r.stock_return.toFixed(2)+'% versus benchmark '+r.benchmark_return.toFixed(2)+'% · difference '+r.difference_pp.toFixed(2)+' percentage points · '+esc(r.start_date)+' → '+esc(r.end_date):esc(r?.reason||'Run a fresh scan for comparison.'))+'</p>';
 }).join('')+'<p>20-session close-to-close returns over identical dates. Positive difference means the stock outperformed; this is not a buy signal.</p>';
}

function resistanceMarkup(plan){
 const r=plan.resistance;if(!r)return '<p>Run a fresh scan for dated resistance evidence.</p>';
 const level=x=>x?money(x.price)+' · pivot '+esc(x.date)+' · confirmed '+esc(x.confirmed_date):'Unavailable';
 return '<h4>Resistance evidence</h4><p>First target: '+level(r.target1)+'</p><p>Second target: '+level(r.target2)+'</p><p>Nearest daily high below the first target: '+(r.nearest_overhead_high?money(r.nearest_overhead_high.price)+' · '+esc(r.nearest_overhead_high.date)+' · possible overhead obstacle; not a confirmed target':'None in the lookback')+'</p><p>'+esc(r.method)+'. Targets are not moved to satisfy reward/risk.</p>';
}

const watchlistResearchPanel=document.createElement('section');watchlistResearchPanel.className='panel card';zonePanel.before(watchlistResearchPanel);
function watchlistValuation(item){
 const v=item.valuation;
 if(v?.status!=='estimated')return 'Unavailable: '+(v?.reason||'Run a fresh scan for valuation evidence');
 return v.classification==='undervalued'?'Supported by model: '+Number(v.valuation_pct).toFixed(2)+'% undervalued · intrinsic estimate '+money(v.intrinsic_value):'Not supported by model: not undervalued · intrinsic estimate '+money(v.intrinsic_value);
}
function renderWatchlistResearch(){
 const items=[...new Map([...(state.golden_zones||[]),...(state.watchlist||[])].map(x=>[x.symbol,x])).values()].sort((a,b)=>a.symbol.localeCompare(b.symbol));
 const field=r=>r?esc(r.status+': '+r.reason)+(r.checked_at?'<br>Checked '+esc(r.checked_at):''):'Unavailable: run a fresh scan';
 watchlistResearchPanel.innerHTML='<h2>Watchlist research · separate from entry readiness</h2><p>Financial and earnings checks run independently of technical entry checks. Model undervaluation is an estimate, not a trade qualification. Checks may be cached for up to one hour; time-budget exclusions remain unavailable.</p>'+(state.stale?'<p><strong>Scan is stale or incomplete. Refresh before relying on these results.</strong></p>':'')+'<div class="tablewrap"><table><thead><tr><th>Stock</th><th>Financial checks</th><th>Earnings</th><th>Undervaluation assessment</th></tr></thead><tbody>'+items.map(x=>'<tr><td>'+esc(x.symbol)+'</td><td style="white-space:normal;min-width:200px">'+field(x.watchlist_research?.financial)+'</td><td style="white-space:normal;min-width:200px">'+field(x.watchlist_research?.earnings)+'</td><td style="white-space:normal;min-width:200px">'+esc(watchlistValuation(x))+'</td></tr>').join('')+'</tbody></table></div>';
}
