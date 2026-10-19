"""Versioned S&P 500 comparison universe; never replaces saved live symbols."""
import csv
from pathlib import Path
from symbols import canonical_symbol, canonical_universe
SOURCE='https://github.com/datasets/s-and-p-500-companies/blob/main/data/constituents.csv'
RETRIEVED='2026-10-19'
def constituents():
    with Path(__file__).with_name('sp500_constituents.csv').open(encoding='utf-8-sig',newline='') as f:
        return sorted({canonical_symbol(r['Symbol']) for r in csv.DictReader(f)})
def scan_universe(configured):
    live=canonical_universe(configured)
    members=constituents()
    # Trial-only work first, so live quotes are collected closest to completion.
    return [s for s in members if s not in set(live)]+live, set(live), members
