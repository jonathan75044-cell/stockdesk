const strategyPanel=document.createElement('section');strategyPanel.className='panel card';
strategyPanel.innerHTML='<h2>Strategy checks and volume comparison</h2><p class="note">Swings are evaluated independently of the put demand-retest gate. Financial, reversal, stop/target, earnings and freshness checks still apply. Volume comparisons are technical pass counts at the same snapshot, not backtests or forecasts; settings remain unchanged.</p><div id="strategy-summary"></div>';
zonePanel.after(strategyPanel);
const renderBeforeStrategySummary=renderRows;
renderRows=function(){renderBeforeStrategySummary();for(const tr of document.querySelectorAll('#rows tr')){const r=state.rows.find(x=>x.symbol===tr.dataset.symbol);for(const small of tr.querySelectorAll('small'))if(small.textContent==='Quality + demand confirmed'&&r?.swing&&!r.demand_zone)small.textContent='Quality + swing checks passed';}const ds=state.diagnostics||[],box=document.getElementById('strategy-summary');box.replaceChildren();
 const measured=ds.filter(d=>d.volume_comparison);
 const add=text=>{const p=document.createElement('p');p.textContent=text;box.append(p)};
 if(!measured.length){add('Awaiting a fresh scan under the independent swing rules.');return;}
 add((state.stale?'STALE / INCOMPLETE · ':'')+measured.length+' stocks reached swing technical comparison. These counts exclude stocks stopped earlier by missing data or liquidity.');
 add('Current volume setting '+state.config.swing_min_rvol+' · swing technical passes '+ds.filter(d=>d.swing_technical_pass).length+' · also passing the older demand gate '+ds.filter(d=>d.legacy_swing_technical_pass).length);
 for(const v of ['1','1.0','1.1','1.3']){if(v==='1'&&measured.some(d=>'1.0' in d.volume_comparison))continue;add('Volume '+v+'×: '+measured.filter(d=>d.volume_comparison[v]).length+' technical passes');}
 const review=state.latest_review;if(review?.swing_stage){let p=document.getElementById('independent-review');if(!p){p=document.createElement('p');p.id='independent-review';p.className='note';document.getElementById('review-body').prepend(p)}p.textContent='Swing: '+(review.stale||review.market_ready===false?'Fresh review required':review.swing_stage)+' · '+(review.swing_blockers||[]).join('; ')+' · Demand confirmation and put trend rows apply to puts.';}
};
const baseDetailWithStrategy=detail;detail=function(sym){baseDetailWithStrategy(sym);const r=state.rows.find(x=>x.symbol===sym);if(r?.swing&&!r.demand_zone){const node=document.querySelector('#detailbody .eyebrow');if(node){const note=document.createElement('p');note.textContent='Independent swing qualification. Put demand retest did not pass; no put is promoted by the swing result.';node.after(note)}}};
