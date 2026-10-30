// Summaries explain evidence; they never change screening or eligibility.
function trialDecisionSummary(trial, scan={}, now=Date.now()){
 const checks=trial.checks||[];
 const failed=stage=>checks.filter(c=>c.stage===stage&&c.status==='fail');
 const missing=checks.filter(c=>c.status!=='pass'&&c.status!=='fail');
 const watch=failed('watch'),entry=failed('ready'),review=failed('confirm');
 const watchMissing=missing.filter(c=>c.stage==='watch');
 const quoteTime=Date.parse(trial.quote_at);
 const oldQuote=!Number.isFinite(quoteTime)||now-quoteTime>900000||quoteTime>now;
 const refresh=!!scan.stale||!scan.completed_at;
 let next;
 if(refresh)next='Run a fresh scan before using these results.';
 else if(watch.length)next='Watchlist blocked: '+watch.map(c=>c.name).join('; ')+'. Recheck after new completed daily data.';
 else if(watchMissing.length)next='Watchlist undecided: obtain evidence for '+watchMissing.map(c=>c.name).join('; ')+'.';
 else if(entry.length||missing.some(c=>c.stage==='ready'))next='Watch only: wait for the entry conditions below; the setup is not confirmed.';
 else next='Technical checks passed: complete the final review and personal risk plan before considering entry.';
 return {watch,entry,review,missing,next,data:refresh?'Stale / incomplete scan':scan.research_only?'Closing-data research; live confirmation pending':oldQuote?'Quote needs refreshing before entry':'Quote within 15 minutes at display time; other checks still apply'};
}
if(typeof module!=='undefined'&&module.exports)module.exports={trialDecisionSummary};
if(typeof document!=='undefined'){
// Shadow results only. No rule toggle or changes to trade eligibility.
var trialComparePanel=document.createElement('section');trialComparePanel.className='panel card';
trialComparePanel.innerHTML='<h2>Current rules vs. Trial rules</h2><p>Practice comparison only. Current rules still control ranked results and alerts. Trial results cannot place trades or qualify a stock.</p><p>Watch = promising pullback. Ready to review = technical checks passed. All required checks passed = research and personal risk checks passed too; not a guarantee.</p><p>The trial uses SPY, a 14-day holding window plus your earnings buffer, and an assumed $0.05 per share round-trip cost. Verified industry financial review, earnings verification, and personal sizing are not connected here and remain unknown.</p><p>The extra filter requires price above the 200-day simple average. Rising or falling compares that average with five sessions ago and does not block a stock. Both trials use the same scan; counts are not performance results.</p><p>Top 25 S&amp;P 500 research candidates. Watch or better comes first, then the stage with the 200-day filter, then the number of passed baseline checks; symbol breaks ties. This is checklist ranking, not expected profit. A “Not ready” row is not a watch recommendation. Constituents use a versioned reference list, not a live index feed.</p><p>Failed means the rule was checked and not met. Information needed means evidence is missing; it is not a failed signal. Watchlist blockers apply to discovery; entry and final-review checks apply later. The 200-day variant is shown separately.</p><label>Find within top 25 <input id="trial-compare-symbol" placeholder="Symbol, e.g. NVDA" maxlength="12"></label><p id="trial-compare-status"></p><div class="tablewrap"><table><thead><tr><th>Rank / Stock</th><th>Current rules</th><th>Trial without 200-day filter</th><th>Trial with 200-day filter</th><th>200-day average</th><th>Decision / next step</th></tr></thead><tbody id="trial-compare-rows"></tbody></table></div>';
document.querySelector('#desk .reports').before(trialComparePanel);
var trialCompareJump=document.createElement('button');trialCompareJump.type='button';trialCompareJump.className='secondary';trialCompareJump.textContent='Current rules vs. Trial rules';
trialCompareJump.onclick=()=>{trialComparePanel.scrollIntoView({behavior:'smooth',block:'start'});document.getElementById('trial-compare-symbol').focus({preventScroll:true})};
document.querySelector('#desk h1').after(trialCompareJump);
function renderTrialComparison(){
 const query=document.getElementById('trial-compare-symbol').value.trim().toUpperCase();
 const all=state.trial_comparison||[];const rows=all.filter(x=>!query||x.symbol===query);
 document.getElementById('trial-compare-status').textContent=(state.stale?'Stale / incomplete scan. ':'')+(state.research_only?'Closing-data research; live entry checks pending. ':'')+'Last completed: '+(state.completed_at||'None')+(all.length?' · '+all.length+' shown · S&P 500 reference list retrieved '+(state.sp500_retrieved||'unknown')+' · '+(state.sp500_universe||[]).length+' members.':' · Run a new scan after deployment.');
 const body=document.getElementById('trial-compare-rows');body.replaceChildren();
 if(!rows.length){const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=6;td.textContent=query?'Not in the displayed top 25. See Agent activity for the full scan.':'No comparison evidence yet.';tr.append(td);body.append(tr)}
 for(const row of rows){
  const tr=document.createElement('tr');const trial=row.trial;
  const current='Ranked swing: '+(row.current_ranked?'Yes':'No')+' · Technical checks: '+(row.current_technical===true?'Passed':row.current_technical===false?'Failed':'Not evaluated')+' · '+row.current+(row.current_preferred?' · Preferred checklist: '+row.current_preferred.status:'');
  const ma=row.sma200||{};const maText=Number.isFinite(ma.value)?money(ma.value)+' · '+(ma.above?'Price above':'Price at or below')+' · '+ma.distance_pct.toFixed(2)+'% · '+ma.direction+' · '+ma.data_date:'Unknown — run a new scan; 200 completed sessions required';
  for(const text of [(row.rank?row.rank+'. ':'')+row.symbol,current,trial?trial.stage:'Not evaluated',row.trial_with_sma200?row.trial_with_sma200.stage:'Not evaluated',maText]){const td=document.createElement('td');td.textContent=text;td.style.whiteSpace='normal';tr.append(td)}
  const cell=document.createElement('td');cell.style.whiteSpace='normal';
  if(!trial)cell.textContent=row.reason;
  else {
   const decision=trialDecisionSummary(trial,state);
   const addText=text=>{const p=document.createElement('p');p.textContent=text;cell.append(p)};
   addText('Next step — '+decision.next);
   addText('Baseline trial: '+decision.watch.length+' watchlist blockers · '+decision.entry.length+' entry conditions waiting · '+decision.review.length+' final-review blockers · '+decision.missing.length+' information items needed');
   for(const [label,list] of [['Watchlist blockers',decision.watch],['Entry conditions still waiting',decision.entry],['Final-review blockers',decision.review],['Information needed',decision.missing]]){
    if(!list.length)continue;
    const heading=document.createElement('strong');heading.textContent=label;cell.append(heading);
    const listNode=document.createElement('ul');
    for(const c of list){const li=document.createElement('li');li.textContent=c.name+(label==='Information needed'?' ('+({watch:'watchlist',ready:'entry',confirm:'final review'}[c.stage]||c.stage)+')':'');listNode.append(li)}
    cell.append(listNode);
   }
   const extra=row.trial_with_sma200?.checks.find(c=>c.name==='Price above 200-day average');
   addText('200-day variant — '+(extra?.status==='pass'?'Extra filter passed.':extra?.status==='fail'?'Additional watchlist blocker: price is at or below its 200-day average.':'Information needed: price versus 200-day average.'));
   addText(decision.data+' · Completed daily data: '+trial.data_date+' · Quote time: '+trial.quote_at);
   const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='View trial checklist and plan';details.append(summary);
   const plan=document.createElement('p');plan.textContent='Hypothetical entry '+money(trial.entry)+' · stop '+money(trial.stop)+' · first resistance '+money(trial.target)+' · obstacle-limited target '+money(trial.effective_target)+' · net reward/risk '+(Number.isFinite(trial.reward_risk)?trial.reward_risk.toFixed(2)+':1':'Unavailable');details.append(plan);
   const ul=document.createElement('ul');for(const c of [...trial.checks,...(row.trial_with_sma200?row.trial_with_sma200.checks.filter(c=>c.name==='Price above 200-day average'):[])]){const li=document.createElement('li');li.textContent=c.stage+' · '+c.name+': '+c.status+' — '+c.detail;ul.append(li)}details.append(ul);cell.append(details);
  }tr.append(cell);body.append(tr);
 }
}
document.getElementById('trial-compare-symbol').oninput=renderTrialComparison;
const renderBeforeTrialComparison=renderRows;renderRows=function(){renderBeforeTrialComparison();renderTrialComparison()};

}
