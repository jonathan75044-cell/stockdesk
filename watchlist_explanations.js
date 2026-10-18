// Explain recorded scan evidence without changing screening or promoting candidates.
function explainWatchlists(snapshot, symbol, priorityOnly=true) {
 const d=(snapshot.diagnostics||[]).find(x=>x.symbol===symbol);
 if(!d)return {demand:'Not evaluated: no recorded scan for this symbol.',golden:'Not evaluated: no recorded scan for this symbol.'};
 const w=(snapshot.watchlist||[]).find(x=>x.symbol===symbol);
 let demand;
 if(w)demand=`Included: intact demand pivot; ${Number(w.distance_atr).toFixed(2)} ATR above zone. ${w.pending||'Bullish retest pending'}.`;
 else if(d.put_demand_pass)demand='Demand already confirmed; this watchlist only contains stocks awaiting a bullish retest. Confirmation alone does not qualify a trade.';
 else if(d.watchlist)demand='Candidate recorded, but omitted from the displayed list after result-limit or quote-freshness filtering.';
 else if(d.demand_rejections?.length)demand='Not included: '+d.demand_rejections.join('; ');
 else demand='Not evaluated or no eligible near-demand candidate recorded. Scan outcome: '+(d.outcome||d.stage||'In progress');
 const p=d.pullback;let golden;
 if(!Object.prototype.hasOwnProperty.call(d,'pullback'))golden='Not evaluated: '+(d.error||d.outcome||d.stage||'Scan in progress');
 else if(!p)golden='No qualifying confirmed swing anchors recorded: latest confirmed high, preceding low 5–60 sessions earlier, and an upward move of at least 2 ATR are required.';
 else {
  const evidence=`Retracement ${(p.retracement*100).toFixed(1)}%; anchors ${p.low_date} → ${p.high_date}; completed daily data ${p.last_bar_date}.`;
  golden=(!p.in_zone?'Outside the 38.2%–61.8% discovery band. ':priorityOnly&&!p.priority?'In discovery band, hidden by the 50%–61.8% priority filter. ':'Included in the pullback band; entry checks are separate. ')+evidence;
 }
 return {demand,golden};
}
if(typeof module!=='undefined')module.exports={explainWatchlists};
if(typeof document!=='undefined'){
 const explanationPanel=document.createElement('section');explanationPanel.className='panel card';
 explanationPanel.innerHTML='<h2>Why a stock is on—or missing from—a watchlist</h2><p>Near demand measures distance from a support pivot in ATR. Golden-zone pullbacks measure Fibonacci retracement of a dated upward swing. These are separate research lists, not trade signals.</p><label>Find stock <input id="watchlist-explanation-symbol" placeholder="Symbol, e.g. NVDA" maxlength="12"></label><p id="watchlist-explanation-status"></p><div class="tablewrap"><table><thead><tr><th>Stock</th><th>Near demand · awaiting retest</th><th>Golden-zone pullback</th></tr></thead><tbody id="watchlist-explanation-rows"></tbody></table></div>';
 document.querySelector('#desk .reports').before(explanationPanel);
 function renderWatchlistExplanations(){
  const filter=document.getElementById('watchlist-explanation-symbol').value.trim().toUpperCase();
  const symbols=filter?[filter]:[...new Set((state.diagnostics||[]).map(d=>d.symbol))].sort();
  document.getElementById('watchlist-explanation-status').textContent=(state.stale?'Stale / incomplete scan. ':'')+'Recorded scan: '+(state.completed_at||'Not completed')+'. Missing symbols may be outside the universe or not yet processed. No checks are inferred.';
  const body=document.getElementById('watchlist-explanation-rows');body.replaceChildren();
  for(const symbol of symbols){const result=explainWatchlists(state,symbol,document.getElementById('golden-only').checked);const row=document.createElement('tr');for(const text of [symbol,result.demand,result.golden]){const cell=document.createElement('td');cell.textContent=text;cell.style.whiteSpace='normal';row.append(cell)}body.append(row)}
 }
 document.getElementById('watchlist-explanation-symbol').oninput=renderWatchlistExplanations;
 document.getElementById('golden-only').addEventListener('change',renderWatchlistExplanations);
 const renderBeforeExplanations=renderRows;renderRows=function(){renderBeforeExplanations();renderWatchlistExplanations()};
}
