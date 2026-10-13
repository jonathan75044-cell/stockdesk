"""Compare demand confirmation frequency; does not change live configuration."""
import argparse
import json
from pathlib import Path
from datetime import date
from engine import demand_zone


def compare(histories,cfg,windows=(5,10,15)):
    totals={str(w):0 for w in windows}
    observations=0
    matches=[]
    for symbol,bars in histories.items():
        dates=[date.fromisoformat(b['date']) for b in bars]
        if dates!=sorted(set(dates)):
            raise ValueError(symbol+': history must have unique dates in ascending order')
        for end in range(65,len(bars)+1):
            days=bars[:end]
            price=float(days[-1]['close'])
            observations+=1
            passed=[]
            for window in windows:
                if demand_zone(price,days,cfg,retest_window=window):
                    totals[str(window)]+=1
                    passed.append(window)
            if passed:matches.append({'symbol':symbol,'date':days[-1]['date'],'windows':passed})
    return {'observations':observations,'demand_confirmations':totals,'matches':matches,
            'note':'Demand-stage frequency only. Uses each historical close and preceding bars; no future bars. Does not test option liquidity, fundamentals, earnings, execution or profitability. Live window remains five sessions.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('history',help='JSON mapping symbols to completed daily OHLCV bars with ISO dates')
    parser.add_argument('--output',default='demand-comparison.json')
    args=parser.parse_args()
    cfg=json.loads(Path(__file__).with_name('config.json').read_text())
    result=compare(json.loads(Path(args.history).read_text()),cfg)
    Path(args.output).write_text(json.dumps(result,indent=2))
