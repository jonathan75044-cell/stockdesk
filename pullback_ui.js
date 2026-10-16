// Read-only discovery list; never promotes a candidate into trade eligibility.
const zonePanel=document.createElement('section');zonePanel.className='panel card';
zonePanel.innerHTML='<h2>Swing pullback watchlist · days to weeks</h2><p>Discovery: 38.2%–61.8% · Priority golden zone: 50%–61.8%. Dated recent daily swing anchors, not 52-week extremes. Independent of fundamental eligibility; membership is not an entry signal.</p><label><input id="golden-only" type="checkbox" checked> Show priority 50%–61.8% only</label><p id="zone-status"></p><div class="tablewrap"><table><thead><tr><th>Stock</th><th>Price</th><th>Retracement</th><th>50%–61.8% band</th><th>Anchor dates</th><th>Evidence / status</th></tr></thead><tbody id="zone-rows"></tbody></table></div>';
document.querySelector('#desk .reports').before(zonePanel);
function renderZones(){
 const rows=(state.golden_zones||[]).filter(r=>!document.getElementById('golden-only').checked||r.priority).sort((a,b)=>Number(b.priority)-Number(a.priority)||a.symbol.localeCompare(b.symbol));
 document.getElementById('zone-status').textContent=(state.stale?'STALE / INCOMPLETE — ':'')+rows.length+' zone candidates. No ranking of best trades without a complete entry plan.';
 const body=document.getElementById('zone-rows');body.replaceChildren();
 for(const r of rows){const tr=document.createElement('tr');const quoteFresh=Date.now()-Date.parse(r.quote_at)>=0&&Date.now()-Date.parse(r.quote_at)<=900000;
 const qualified=state.rows.find(x=>x.symbol===r.symbol&&x.swing);
 for(const value of [r.symbol,money(r.price),(100*r.retracement).toFixed(1)+'%',money(r.zone_low)+' – '+money(r.priority_high),r.low_date+' → '+r.high_date,
 (state.stale||!quoteFresh?'Fresh review required':qualified?'Meets trade checks':r.swing_stage||'In zone · awaiting confirmation')+' · '+(r.swing_blockers||[]).join('; ')+' · '+r.source+' · quote '+r.quote_at]){const td=document.createElement('td');td.textContent=value;tr.append(td)}
 tr.title=r.method;body.append(tr);}
}
const renderBeforeZones=renderRows;renderRows=function(){renderBeforeZones();renderZones()};
document.getElementById('golden-only').onchange=renderZones;
