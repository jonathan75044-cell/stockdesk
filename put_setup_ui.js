// Preferred put assessment. Personal confirmations are local to this review,
// never broker balances, orders, or permission to place a trade.
function assessPreferredPut(review, option, inputs, now=Date.now()){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const positive=x=>finite(x)&&x>0;
 const checks=[];
 const add=(name,pass,evidence)=>checks.push({name,status:pass===null?'unknown':pass?'pass':'fail',value:evidence,requirement:name});
 const requiredStock=['Regular market session','Underlying quote freshness','Completed daily history','Minimum stock price','Average volume','Demand confirmation','Annual fundamental gate','Put trend'];
 const requiredOption=['Standard put','Quote freshness','DTE','Absolute delta','Bid/ask validity','Cash collateral','Open interest','Daily option volume','OTM distance %','Demand-zone strike','Dollar spread','Spread %','Premium yield %','Earnings exclusion'];
 for(const [source,names] of [[review.checks,requiredStock],[option.checks,requiredOption]])for(const name of names){
  const c=(source||[]).find(c=>c.name===name);
  add(name,c?.status==='pass'?true:c?.status==='fail'?false:null,c?.value??'Missing evidence');
 }
 const end=Date.parse(review.clock?.regular_session_end);
 const quote=review.quote?.trade_date;
 const optTime=option.quote_timestamp*1000;
 const completed=Date.parse(review.completed_at);
 const current=review.status==='Completed'&&review.clock?.state==='open'&&Number.isFinite(end)&&now<end&&finite(quote)&&now>=quote&&now-quote<=900000&&Number.isFinite(optTime)&&now>=optTime&&now-optTime<=900000&&Number.isFinite(completed)&&now>=completed&&now-completed<=900000;
 add('Live review and quotes within 15 minutes',current,'After-hours or expired evidence cannot pass.');
 const v=review.valuation||{},strike=option.strike,lower=review.demand_zone?.low;
 add('Strike below supported intrinsic estimate',v.status==='estimated'&&positive(v.intrinsic_value)&&positive(strike)?strike<v.intrinsic_value:null,v.status==='estimated'?'Intrinsic estimate '+v.intrinsic_value:(v.reason||'Valuation unavailable'));
 add('Strike at or below support floor',positive(strike)&&positive(lower)?strike<=lower:null,positive(lower)?'Support floor '+lower:'Confirmed support unavailable');
 add('Daily option volume at least 100 contracts',finite(option.volume)?option.volume>=100:null,option.volume??'Unavailable');
 const n=inputs.contracts,validCount=Number.isInteger(n)&&n>=1;
 const collateral=validCount&&positive(strike)?n*100*strike:null;
 add('Whole contract count',validCount,n);
 add('Full collateral in confirmed uncommitted cash',positive(inputs.cash)&&collateral!==null?inputs.cash>=collateral:null,collateral===null?'Collateral unavailable':'Required cash '+collateral+'; supplied '+(inputs.cash??'unknown'));
 add('Within remaining allocation budget for this stock',positive(inputs.allocation)&&collateral!==null?inputs.allocation>=collateral:null,inputs.allocation??'Enter budget after existing holdings and orders');
 add('Willing to own all assigned shares at this strike',inputs.willing===true?true:null,validCount?n*100+' shares at '+strike:'Confirm contract count');
 add('Profit-taking and deterioration/assignment plan recorded',positive(inputs.profit)&&inputs.profit<=100&&typeof inputs.exit==='string'&&inputs.exit.trim().length>0?true:null,'Specify premium capture % and what you will do if the stock falls or assignment approaches.');
 const passed=checks.every(c=>c.status==='pass');
 return {status:passed?'Put checks passed':'Put watchlist candidate',checks,collateral,passed};
}

if(typeof module!=='undefined'&&module.exports)module.exports={assessPreferredPut};
if(typeof document!=='undefined'){
 let activePutChecklist=null;
 const priorPutEvidence=renderOptionEvidence;
 function updatePutChecklist(){
  const root=document.getElementById('preferred-put-result');
  if(!root||!activePutChecklist)return;
  const r=state.latest_review;
  if(!r||r.completed_at!==activePutChecklist.completed||r.symbol!==activePutChecklist.symbol){root.textContent='Review changed. Select a contract again.';return;}
  const o=(r.options||[]).find(o=>o.contract===activePutChecklist.contract);
  if(!o){root.textContent='Contract unavailable. Review again.';return;}
  const num=id=>{const value=document.getElementById(id).value;return value===''?null:Number(value)};
  const a=assessPreferredPut(r,o,{contracts:num('put-plan-count'),cash:num('put-plan-cash'),allocation:num('put-plan-allocation'),willing:document.getElementById('put-plan-willing').checked,profit:num('put-plan-profit'),exit:document.getElementById('put-plan-exit').value});
  root.innerHTML='<h4>'+esc(a.status)+'</h4><p>'+esc(o.preferred_liquidity===true?'Preferred open interest met.':'Open interest preference not met or unavailable; 500 remains the minimum.')+'</p><p>Based on this review and your inputs. Cash and allocation are not verified broker balances. No order is placed.</p>'+criteriaTable(a.checks);
 }
 renderOptionEvidence=function(o,r){
  priorPutEvidence(o,r);
  activePutChecklist={contract:o.contract,symbol:r.symbol,completed:r.completed_at};
  const panel=document.createElement('section');panel.className='card';panel.id='preferred-put-panel';
  panel.innerHTML='<h3>Preferred cash-secured-put setup</h3><p>Confirm ownership price, support, valuation, earnings, liquidity and your cash plan before comparing premium. Inputs apply only to this selected review and reset when you select a contract again.</p><label>Contracts <input id="put-plan-count" type="number" min="1" step="1" value="1"></label><label>Confirmed uncommitted cash ($) <input id="put-plan-cash" type="number" min="0" step="any"></label><label>Remaining allocation budget for this stock ($) <input id="put-plan-allocation" type="number" min="0" step="any"></label><label><input id="put-plan-willing" type="checkbox"> I am willing to own all assigned shares at this strike, including after a decline.</label><label>Planned premium capture before closing (%) <input id="put-plan-profit" type="number" min="0" max="100" step="any"></label><label>Plan if support breaks, losses grow, or assignment approaches <textarea id="put-plan-exit"></textarea></label><p>7–45 calendar days to expiration is the starting range. Shorter expirations leave less time to respond; assignment may occur before expiration. Premium is the maximum gain; a large stock decline can greatly exceed it. Review the downside scenarios below.</p><div id="preferred-put-result"></div>';
  document.getElementById('option-evidence').prepend(panel);
  panel.querySelectorAll('input,textarea').forEach(el=>el.oninput=updatePutChecklist);
  updatePutChecklist();
 };
 const priorPutChecklistRows=renderRows;
 renderRows=function(){priorPutChecklistRows();updatePutChecklist()};
}
