"""Read-only check of current SEC annual evidence; does not change scanner state."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from provider import parse_annual_quality,FundamentalDataError
from sec_fundamentals import load_annual_payload,SECDataError
from engine import fundamental_gate


if __name__=='__main__':
    today=datetime.now(ZoneInfo('America/New_York')).date()
    audit={}
    try:
        payload,audit=load_annual_payload('DE',today)
        quality=parse_annual_quality(payload,today)
        quality.update(source='SEC EDGAR annual 10-K companyfacts',sec_audit=audit)
        cfg=json.loads(Path(__file__).with_name('config.json').read_text())
        reasons=[]
        passed=fundamental_gate({'quality':quality},cfg,today,reasons) is not None
        report={'result':'Current annual evidence parsed','quality':quality,
                'default_fundamental_gate_passed':passed,'default_fundamental_rejections':reasons,
                'note':'Uses packaged config.json for this probe. Live scanner also merges saved settings. Demand, trend, earnings and options are not checked; this is not trade qualification.'}
    except (SECDataError,FundamentalDataError) as error:
        report={'result':'Excluded: required evidence unavailable or invalid',
                'reason':str(error),'sec_audit':{**audit,**error.details}}
    Path('sec-de-probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
