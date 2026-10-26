const {chromium}=require('playwright');
const fs=require('fs'),assert=require('assert');
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const imported=[{date:'2026-10-26',account:'Test',legs:[{symbol:'TEST',asset:'EQUITY',quantity:-10,price:110,effect:'CLOSING'}],net_amount:1099,status:'VALID',description:'Trade',profit:98,profit_note:'FIFO estimate'}, {date:'2026-10-26',account:'Test',legs:[],profit:-20,profit_note:'FIFO estimate',description:'Loss',status:'VALID'}, {date:'2026-10-26',account:'Test',legs:[],profit:null,profit_note:'Unavailable: missing entry',description:'Unmatched',status:'VALID'}];
await page.route('http://journal.test/**',route=>{const p=new URL(route.request().url()).pathname;
if(p==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync('journal.html','utf8')});
const value=p==='/api/journal/schwab'?{entries:imported,enabled:true,status:{message:'Test sync'}}:{entries:[{symbol:'TEST',strategy:'Swing shares',status:'Closed',quantity:10,opened:'2026-10-26',pnl:50}]};
return route.fulfill({contentType:'application/json',body:JSON.stringify(value)});});
await page.goto('http://journal.test/');await page.locator('#brokerrows tr').first().waitFor({state:'visible'});
assert.equal(await page.locator('#brokerprofit').innerText(),'$78.00');assert.equal(await page.locator('#brokermatched').innerText(),'2');assert.equal(await page.locator('#brokerunmatched').innerText(),'1');assert.equal(await page.locator('#pnl').innerText(),'$50.00');
assert((await page.locator('#brokerrows').innerText()).includes('Unavailable'));assert((await page.locator('#brokerrows').innerText()).includes('-$20.00'));
await page.locator('#search').fill('MISSING');assert.equal(await page.locator('#pnl').innerText(),'$50.00');
assert.deepEqual(errors,[]);console.log('Journal profit columns, losses, unavailable entries and separate totals passed.');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
