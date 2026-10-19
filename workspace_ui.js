// Move existing panels without recreating their controls or render handlers.
const watchWorkspace=document.createElement('div');watchWorkspace.id='watch-workspace';watchWorkspace.className='hidden';
const watchHeading=document.createElement('h1');watchHeading.textContent='Watchlists & rule comparison';watchWorkspace.append(watchHeading);
const watchTabs=document.createElement('div');watchTabs.setAttribute('role','tablist');watchTabs.setAttribute('aria-label','Research lists');watchTabs.style.display='flex';watchTabs.style.flexWrap='wrap';watchTabs.style.gap='8px';watchWorkspace.append(watchTabs);watchWorkspace.append(tableNote);
const watchPages=[['Near-demand watchlist',watchPanel],['Golden-zone watchlist',zonePanel],['Current rules vs. Trial rules',trialComparePanel],['Watchlist research',watchlistResearchPanel]];
function selectWatchTab(index,focus=false){watchPages.forEach(([label,panel],i)=>{panel.hidden=i!==index;const b=watchTabs.children[i];b.setAttribute('aria-selected',String(i===index));b.tabIndex=i===index?0:-1;b.className=i===index?'':'secondary'});if(focus)watchTabs.children[index].focus()}
watchPages.forEach(([label,panel],i)=>{const b=document.createElement('button');b.type='button';b.textContent=label;b.id='watch-tab-'+i;b.setAttribute('role','tab');b.setAttribute('aria-controls','watch-page-'+i);panel.id='watch-page-'+i;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',b.id);b.onclick=()=>selectWatchTab(i);b.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();selectWatchTab(e.key==='Home'?0:e.key==='End'?watchPages.length-1:(i+(e.key==='ArrowRight'?1:watchPages.length-1))%watchPages.length,true)}};watchTabs.append(b);watchWorkspace.append(panel)});
document.querySelector('main').append(watchWorkspace);
const watchNav=document.createElement('button');watchNav.textContent='Watchlists & trial rules';watchNav.onclick=()=>page('watch-workspace',watchNav);document.querySelector('aside nav').append(watchNav);
trialCompareJump.onclick=()=>{page('watch-workspace',watchNav);selectWatchTab(2);document.getElementById('trial-compare-symbol').focus()};
selectWatchTab(0);
const rankedExplanation=document.createElement('p');rankedExplanation.id='ranked-explanation';rankedExplanation.setAttribute('role','status');document.getElementById('rows').closest('.panel').querySelector('.panelhead').after(rankedExplanation);
function explainRanked(snapshot){
 if((snapshot.rows||[]).length)return 'These stocks passed the current scan gates. Watchlist membership alone does not qualify a trade.';
 const counts={};for(const d of snapshot.diagnostics||[]){if(d.trial_only)continue;const reason=d.outcome||'Not evaluated';counts[reason]=(counts[reason]||0)+1}
 const reasons=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([reason,n])=>n+' '+reason).join(' Â· ');
 return (snapshot.stale?'Scan is stale or incomplete. ':'')+'No ranked opportunities in this snapshot. '+(reasons?'Recorded current-rule outcomes: '+reasons+'. ':'Run a fresh scan to collect reasons. ')+'Watchlists contain candidates still waiting for checks; trial-only S&P 500 stocks cannot enter this table.';
}
const renderBeforeWorkspace=renderRows;renderRows=function(){renderBeforeWorkspace();rankedExplanation.textContent=explainRanked(state)};
