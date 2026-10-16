"""Verified issuer aliases and the user-confirmed NUFG typo correction."""
def canonical_symbol(symbol):
    symbol=symbol.strip().upper()
    return {'BRK-B':'BRK.B','BRK/B':'BRK.B','SQ':'XYZ','NUFG':'MUFG'}.get(symbol,symbol)

def canonical_universe(value):
    return list(dict.fromkeys(canonical_symbol(s) for s in value.split()))
