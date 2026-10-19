// Shadow results only. No rule toggle or changes to trade eligibility.
const trialComparePanel=document.createElement('section');trialComparePanel.className='panel card';
trialComparePanel.innerHTML='<h2>Current rules vs. Trial rules</h2><p>Practice comparison only. Current rules still control ranked results and alerts. Trial results cannot place trades or qualify a stock.</p><p>Watch = promising pullback. Ready to review = technical checks passed. All required checks passed = research and personal risk checks passed too; not a guarantee.</p><p>The trial uses SPY, a 14-day holding window plus your earnings buffer, and an assumed $0.05 per share round-trip cost. Verified industry financial review, earnings verification, and personal sizing are not connected here and remain unknown.</p><label>Compare stock <input id="trial-compare-symbol" placeholder="Symbol, e.g. NVDA" maxlength="12"></label><p id="trial-compare-status"></p><div class="tablewrap"><table><thead><tr><th>Stock</th><th>Current rules</th><th>Trial rules</th><th>Why / checks</th></tr></thead><tbody id="trial-compare-rows"></tbody></table></div>';
document.querySelector('#desk .reports').before(trialComparePanel);
const trialCompareJump=document.createElement('button');trialCompareJump.type='button';trialCompareJump.className='secondary';trialCompareJump.textContent='Current rules vs. Trial rules';
trialCompareJump.onclick=()=>{trialComparePanel.scrollIntoView({behavior:'smooth',block:'start'});document.getElementById('trial-compare-symbol').focus({preventScroll:true})};
document.querySelector('#desk h1').after(trialCompareJump);
function renderTrialComparison(){
 const query=document.getElementById('trial-compare-symbol').value.trim().toUpperCase();
 const all=state.trial_comparison||[];const rows=all.filter(x=>!query||x.symbol===query);
 document.getElementById('trial-compare-status').textContent=(state.stale?'Stale / incomplete scan. ':'')+(state.research_only?'Closing-data research; live entry checks pending. ':'')+'Last completed: '+(state.completed_at||'None')+(all.length?' · '+all.length+' recorded stocks.':' · Run a new scan after deployment.');
 const body=document.getElementById('trial-compare-rows');body.replaceChildren();
 if(!rows.length){const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=4;td.textContent=query?'No scan record for this symbol. It may be outside your screening universe.':'No comparison evidence yet.';tr.append(td);body.append(tr)}
 for(const row of rows){
  const tr=document.createElement('tr');const trial=row.trial;
  const current='Ranked swing: '+(row.current_ranked?'Yes':'No')+' · Technical checks: '+(row.current_technical===true?'Passed':row.current_technical===false?'Failed':'Not evaluated')+' · '+row.current+(row.current_preferred?' · Preferred checklist: '+row.current_preferred.status:'');
  for(const text of [row.symbol,current,trial?trial.stage:'Not evaluated']){const td=document.createElement('td');td.textContent=text;td.style.whiteSpace='normal';tr.append(td)}
  const cell=document.createElement('td');cell.style.whiteSpace='normal';
  if(!trial)cell.textContent=row.reason;
  else {const blocked=trial.checks.filter(c=>c.status!=='pass');const p=document.createElement('p');p.textContent=blocked.length+' failed or unknown checks · daily data '+trial.data_date+' · quote '+trial.quote_at;cell.append(p);
   const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent='View trial checklist and plan';details.append(summary);
   const plan=document.createElement('p');plan.textContent='Hypothetical entry '+money(trial.entry)+' · stop '+money(trial.stop)+' · first resistance '+money(trial.target)+' · obstacle-limited target '+money(trial.effective_target)+' · net reward/risk '+(Number.isFinite(trial.reward_risk)?trial.reward_risk.toFixed(2)+':1':'Unavailable');details.append(plan);
   const ul=document.createElement('ul');for(const c of trial.checks){const li=document.createElement('li');li.textContent=c.stage+' · '+c.name+': '+c.status+' — '+c.detail;ul.append(li)}details.append(ul);cell.append(details);
  }tr.append(cell);body.append(tr);
 }
}
document.getElementById('trial-compare-symbol').oninput=renderTrialComparison;
const renderBeforeTrialComparison=renderRows;renderRows=function(){renderBeforeTrialComparison();renderTrialComparison()};
