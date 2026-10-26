"""Conservative FIFO estimates from single-instrument posted broker cash flows.
No position, tax-lot, corporate-action or assignment reconciliation is implied.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime

def number(value):
    if isinstance(value,bool) or value is None: return None
    try:
        n=Decimal(str(value))
        return n if n.is_finite() else None
    except (InvalidOperation,ValueError): return None

def estimates(records):
    rows=deepcopy(records);lots={};blocked=set()
    def keys(row):
        return [(row.get('account'),l.get('asset'),l.get('symbol')) for l in row.get('legs',[])]
    def stamp(row):
        try:
            dt=datetime.fromisoformat(row['date'].replace('Z','+00:00'))
            return dt.timestamp() if dt.tzinfo else None
        except (ValueError,KeyError,TypeError): return None
    # Undated activity cannot be placed reliably in a lot sequence.
    for row in rows:
        if stamp(row) is None: blocked.update(keys(row))
    for row in sorted(rows,key=lambda r:(stamp(r) or 0,str(r.get('activity_id','')))):
        row.update(profit=None,profit_note='Unavailable: cannot safely match this activity.')
        ks=keys(row);legs=row.get('legs',[])
        if row.get('status')!='VALID':
            row['profit_note']='Unavailable: activity is not confirmed VALID.'
            blocked.update(ks);continue
        description=row.get('description','').lower()
        if len(legs)!=1 or any(w in description for w in ('assign','expir','exercise','split','reorganiz')):
            row['profit_note']='Unavailable: multi-leg, assignment, expiry or corporate-action reconciliation required.'
            blocked.update(ks);continue
        leg=legs[0];key=ks[0];qty=number(leg.get('quantity'));cash=number(row.get('net_amount'))
        if key in blocked or not all(key) or qty is None or not qty or cash is None:
            blocked.add(key);continue
        effect=leg.get('effect');direction=1 if qty>0 else -1;size=abs(qty)
        if effect not in ('OPENING','CLOSING') or cash*qty>0:
            row['profit_note']='Unavailable: missing position effect or inconsistent cash direction.'
            blocked.add(key);continue
        queue=lots.setdefault(key,[])
        if effect=='OPENING':
            if any(l['direction']!=direction for l in queue):
                blocked.add(key);continue
            queue.append(dict(direction=direction,quantity=size,cash=cash))
            row['profit_note']='Open position: profit is recorded when a matching close is imported.'
            continue
        if any(l['direction']==direction for l in queue) or sum((l['quantity'] for l in queue),Decimal(0))<size:
            row['profit_note']='Unavailable: matching opening quantity is missing from imported history.'
            blocked.add(key);continue
        remaining=size;profit=cash
        while remaining:
            lot=queue[0];used=min(remaining,lot['quantity']);allocated=lot['cash']*used/lot['quantity']
            profit+=allocated;lot['quantity']-=used;lot['cash']-=allocated;remaining-=used
            if not lot['quantity']:queue.pop(0)
        row['profit']=float(profit.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
        row['profit_note']='FIFO estimate for this closing quantity, using allocated entry and exit net cash including posted costs.'
    return rows
