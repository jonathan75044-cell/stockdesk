// These labels describe recorded evidence; they never change scanner eligibility.
function confirmationStatus(item,{watch=false,stale=false,review=false}={}){
    if(stale||item.stale||item.market_ready===false)return 'Fresh review required';
    if(review&&item.status!=='Completed')return 'Checks pending';
    if(watch)return 'Awaiting confirmation';
    const zone=item.demand_zone;
    if(!zone)return review&&(item.checks||[]).some(c=>c.name==='Demand confirmation'&&c.status==='fail')?'Awaiting confirmation':'Confirmation unavailable';
    if(item.swing_eligible||item.eligible_contract_count>0||item.swing||item.put){
        if(review)return item.swing_eligible||item.eligible_contract_count>0?'Meets recorded filters':'Confirmed — blocked / missing data';
        return 'Meets recorded filters';
    }
    return review?'Confirmed — blocked / missing data':'Confirmed — checks pending';
}
function tradingViewUrl(symbol){
    if(!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(symbol))return null;
    return 'https://www.tradingview.com/chart/?symbol='+encodeURIComponent(symbol);
}
function chartLink(symbol){
    const url=tradingViewUrl(symbol);return url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer" title="Verify the exchange and share class in TradingView">Open in TradingView</a>':'';
}
function confirmationEvidence(item,options={}){
    const zone=item.demand_zone||item.zone;
    return '<b>'+esc(confirmationStatus(item,options))+'</b>'+(zone?'<br><small>Zone '+money(zone.low)+' – '+money(zone.high)+'<br>Confirmation: '+esc(zone.confirmed_date||'pending')+'<br>Invalidation: lower low below '+money(zone.low)+'</small>':'');
}
const confirmationGuide=document.createElement('section');confirmationGuide.className='card';confirmationGuide.style.margin='16px 0';
confirmationGuide.innerHTML='<h3>Confirmation before entry</h3><p><b>Awaiting confirmation:</b> a recent completed bullish retest is still required. <b>Confirmed — checks pending:</b> demand passed, but later requirements remain. <b>Meets recorded filters:</b> all recorded requirements passed for the indicated strategy; verify fresh broker quotes, earnings and personal sizing before entry.</p><p class="note">A TradingView alert is a request to recheck evidence. It does not confirm the demand zone or make a stock eligible. A swing also requires its existing breakout and hold checks; a put requires its own trend, earnings and contract checks. No new entry rule has been substituted.</p>';
researchPanel.before(confirmationGuide);
const tvPanel=document.createElement('section');tvPanel.className='card';tvPanel.style.margin='16px 0';
tvPanel.innerHTML='<h3>TradingView alerts</h3><p id="tv-connection"></p><p class="note">Configure the webhook using TRADINGVIEW_ALERTS_SETUP.md in the update package. Use your signed-in TradingView account. An alert requests independent review, never an order. Received signals and review outcomes appear below.</p><div id="tv-events"></div>';
$('activity').append(tvPanel);
function renderTradingViewEvents(){
    const tv=state.tradingview||{};$('tv-connection').textContent=tv.configured?'Webhook receiver configured. Check TradingView’s alert log for delivery status.':'Webhook receiver disabled — set the dedicated token in Render first.';
    $('tv-events').innerHTML=(tv.events||[]).slice().reverse().map(e=>'<p><b>'+esc(e.symbol)+'</b> · '+esc(e.trigger)+' · '+esc(e.status)+'<br>'+esc(new Date(e.received_at*1000).toLocaleString())+' · Signal price '+money(e.signal_price)+(e.status==='Reviewed'?'<br>At review time: '+Number(e.eligible_contract_count||0)+' contracts met filters; swing '+(e.swing_eligible?'met filters':'blocked / unavailable')+'. Historical result — review again before entry.':'')+'</p>').join('')||'<p>No TradingView signals received yet.</p>';
}
const renderBeforeConfirmation=renderRows;
renderRows=function(){
    renderBeforeConfirmation();
    const add=(tr,item,watch)=>{
        const cell=document.createElement('td');cell.innerHTML=confirmationEvidence(item,{watch,stale:state.stale||state.status==='Scanning'||/Market closed/i.test(state.status||'')})+'<br>'+chartLink(item.symbol);tr.append(cell);
        cell.querySelector('a')?.addEventListener('click',e=>e.stopPropagation());
    };
    for(const tr of document.querySelectorAll('#rows tr')){const item=state.rows.find(r=>r.symbol===tr.dataset.symbol);if(item)add(tr,item,false)}
    Array.from(watchBody.children).forEach((tr,i)=>{const item=(state.watchlist||[])[i];if(item)add(tr,item,true)});
    const r=state.latest_review;
    if(r){let panel=$('review-confirmation');if(!panel){panel=document.createElement('section');panel.id='review-confirmation';panel.className='banner';$('review-body').prepend(panel)}panel.innerHTML=confirmationEvidence(r,{review:true})+'<p>'+chartLink(r.symbol)+'</p><small>Chart link uses the stock symbol. Verify the exchange and share class; chart feeds can differ from Schwab.</small>';}
    renderTradingViewEvents();
};
for(const row of [document.getElementById('rows').closest('table').querySelector('thead tr'),watchHeadRow]){const th=document.createElement('th');th.textContent='Confirmation / chart';row.append(th)}
