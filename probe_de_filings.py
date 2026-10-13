"""Read-only Finnhub coverage probe. Uses FINNHUB_TOKEN; never prints it."""
import json
import os
import time
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from pathlib import Path


def filing_summary(payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
        return {'result':'Unsupported response or provider error; raw text withheld'}
    data=payload['data']
    if any(not isinstance(row,dict) for row in data):
        return {'result':'Unsupported filing record shape'}
    filings=[{k:row.get(k) for k in ('endDate','filedDate','form','cik','accessNumber','year','quarter')}
             for row in data]
    filings.sort(key=lambda row:(str(row.get('endDate') or ''),str(row.get('filedDate') or '')),reverse=True)
    return {'result':'Returned filings' if filings else 'No filings',
            'response_symbol':payload.get('symbol'),'response_cik':payload.get('cik'),
            'filing_count':len(filings),'latest_period':filings[0]['endDate'] if filings else None,
            'filings':filings[:12]}


def probe(token,params):
    request=Request('https://finnhub.io/api/v1/stock/financials-reported?'+urlencode(params),
                    headers={'X-Finnhub-Token':token,'Accept':'application/json'})
    try:
        with urlopen(request,timeout=30) as response:
            payload=json.load(response)
            return {'http_status':response.status,**filing_summary(payload)}
    except HTTPError as error:
        return {'http_status':error.code,'result':'Request rejected; check plan/access for 403 or rate limits for 429'}
    except (URLError,TimeoutError,OSError):
        return {'result':'Network request failed; details withheld to avoid credential disclosure'}
    except (ValueError,TypeError):
        return {'result':'Invalid JSON response; raw text withheld'}


def main():
    token=os.environ.get('FINNHUB_TOKEN','').strip()
    if not token:raise SystemExit('FINNHUB_TOKEN is not set. Run this in the scanner environment; do not paste the key into chat.')
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'endpoint':'stock/financials-reported',
            'frequency':'annual','probes':[]}
    checks=[('DE ticker',{'symbol':'DE','freq':'annual'}),
            ('Deere SEC identifier',{'cik':'0000315189','freq':'annual'}),
            ('AAPL control',{'symbol':'AAPL','freq':'annual'})]
    for name,params in checks:
        result={'name':name,'query':params,**probe(token,params)}
        report['probes'].append(result)
        print(name+': '+json.dumps({k:v for k,v in result.items() if k not in ('filings','query')},ensure_ascii=True))
        time.sleep(1.2)
    output=Path('de-filing-probe.json')
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Saved de-filing-probe.json. This report contains only public filing metadata and response status.')


if __name__=='__main__':main()
