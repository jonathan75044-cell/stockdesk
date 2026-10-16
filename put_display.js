// Display calculations only: never changes screening, eligibility, alerts or orders.
function putDisplayMetrics(p){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const valid=p&&finite(p.bid)&&finite(p.ask)&&p.bid>0&&p.ask>=p.bid&&finite(p.strike)&&p.strike>0;
 const period=valid?100*p.bid/p.strike:null;
 return {midpoint:valid?(p.bid+p.ask)/2:null,periodYield:period,
   weeklyYield:period!==null&&finite(p.dte)&&p.dte>0?period*7/p.dte:null};
}
const putDisplayPercent=x=>typeof x==='number'&&Number.isFinite(x)?x.toFixed(2)+'%':'N/A';
function putQuoteLabel(seconds){
 if(typeof seconds!=='number'||!Number.isFinite(seconds)||seconds<=0)return 'Unavailable';
 const d=new Date(seconds*1000);if(Number.isNaN(d.getTime()))return 'Unavailable';
 const age=Date.now()-d.getTime();
 return d.toLocaleString('en-US',{timeZone:'America/Chicago',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'})+(age<0?' · future timestamp':age>900000?' · stale':'');
}
const putDisplayColumns=['Expiry / DTE','Bid / Ask','Midpoint / share','Bid period yield','Weekly-equivalent yield','Option quote · Chicago'];
function putDisplayCells(p){const m=putDisplayMetrics(p);return [p?(p.expiry||'N/A')+' / '+(p.dte??'N/A')+'d':'—',p?money(p.bid)+' / '+money(p.ask):'—',money(m.midpoint),putDisplayPercent(m.periodYield),putDisplayPercent(m.weeklyYield),p?putQuoteLabel(p.quote_timestamp):'—'];}
function appendPutDisplay(tr,p){for(const value of putDisplayCells(p)){const td=document.createElement('td');td.textContent=value;tr.append(td)}}
const putTable=document.getElementById('rows').closest('table');
for(const label of putDisplayColumns){const th=document.createElement('th');th.textContent=label;putTable.querySelector('thead tr').append(th)}
const putNote=document.createElement('p');putNote.className='note';putNote.textContent='Put yields use the quoted bid ÷ strike, before fees. Weekly equivalent = period yield × 7 ÷ scan DTE: a simple comparison, not a promised weekly return. Midpoint is an indicative quote, not an assured fill. Option time is the older bid/ask timestamp from Schwab; stock timestamps are separate in details. Missing values remain N/A. Screening rules are unchanged.';
putTable.closest('.panel').append(putNote);
const renderBeforePutDisplay=renderRows;
renderRows=function(){renderBeforePutDisplay();for(const tr of document.querySelectorAll('#rows tr'))appendPutDisplay(tr,state.rows.find(r=>r.symbol===tr.dataset.symbol)?.put);
 const review=state.latest_review;
 for(const b of document.querySelectorAll('#review-body [data-option]')){const tr=b.closest('tr');if(tr.dataset.putDisplay)continue;const table=tr.closest('table');if(!table.dataset.putDisplay){for(const label of putDisplayColumns){const th=document.createElement('th');th.textContent=label;table.querySelector('thead tr').append(th)}table.dataset.putDisplay='1';const note=putNote.cloneNode(true);table.parentElement.after(note)}appendPutDisplay(tr,review?.options?.[Number(b.dataset.option)]);tr.dataset.putDisplay='1';}
};
const detailBeforePutDisplay=detail;
detail=function(sym){detailBeforePutDisplay(sym);const r=state.rows.find(x=>x.symbol===sym);if(!r?.put)return;const section=document.createElement('section');const h=document.createElement('h3');h.textContent='Put pricing and yield comparison';section.append(h);const values=putDisplayCells(r.put);const list=document.createElement('dl');putDisplayColumns.forEach((label,i)=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=values[i];list.append(dt,dd)});section.append(list,putNote.cloneNode(true));document.querySelector('#detailbody .details').append(section)};
