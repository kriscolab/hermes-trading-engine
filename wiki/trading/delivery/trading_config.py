"""
Shared configuration for the trading platform.
Single source of truth for regime thresholds, ticker universe, and thesis metadata.
Imported by dashboard, risk engine, and edge generator.
"""
from pathlib import Path

TRADING_DIR = Path(__file__).resolve().parent.parent

# ── Regime-Adaptive Thresholds ──
REGIME_THRESHOLDS = {
    "RISK_ON":    {"t1": 0.15, "t2": 0.25, "sl": -0.18},
    "TRENDING":   {"t1": 0.10, "t2": 0.20, "sl": -0.15},
    "NEUTRAL":    {"t1": 0.08, "t2": 0.15, "sl": -0.12},
    "CAUTIOUS":   {"t1": 0.05, "t2": 0.10, "sl": -0.08},
    "RISK_OFF":   {"t1": 0.03, "t2": 0.06, "sl": -0.05},
}

# ── Ticker Universe (dynamically loaded from HL universe) ──
def _load_crypto_tickers():
    """Load top crypto tickers from Hyperliquid universe, fallback to hardcoded.
    Limits to top 50 by volume to keep quant-aggregator runtime reasonable."""
    import json
    hl_path = Path("/tmp/hl_universe.json")
    if hl_path.exists():
        data = json.loads(hl_path.read_text())
        native = data.get("native", [])
        # Sort by volume, take top 50
        native.sort(key=lambda a: a.get("volume24h", 0), reverse=True)
        return [a["name"] for a in native[:50]]
    return ["BTC","ETH","SOL","HYPE","XRP","DOGE","AVAX","LINK","ADA",
            "NEAR","TON","SUI","APT","ARB","OP","MATIC","DOT","ATOM",
            "WIF","BONK","PEPE","SHIB","SEI","INJ","TIA","RUNE","FET",
            "RNDR","TAO","WLD","STRK","JUP","PYTH","JTO","ENA","PENDLE",
            "LDO","AAVE","UNI","CRV","SNX","GMX","DYDX","MKR","COMP",
            "LTC","BCH","ETC","FIL","ICP","QNT","ZEC","LIT","ZRO"]

CRYPTO_TICKERS = _load_crypto_tickers()
EQUITY_TICKERS = ["GLD", "IBIT", "ETHA", "SOXX", "IGV", "DTCR", "TAN", "XLC", "XLE"]

# ── Thesis Metadata ──
THESIS_FILES = {
    "commodity": TRADING_DIR / "theses" / "commodity-super-cycle" / "signals.md",
    "crypto":    TRADING_DIR / "theses" / "crypto-native" / "signals.md",
    "ai":        TRADING_DIR / "theses" / "ai-supercycle" / "signals.md",
}

# ── Data File Paths ──
DATA_PATHS = {
    "portfolio_prices": Path("/tmp/portfolio_prices.json"),
    "crypto_module":    Path("/tmp/crypto_module_data.json"),
    "live_market":      Path("/tmp/live_market_data.json"),
    "quant_signals":    Path("/tmp/quant_signals.json"),
    "edge_generator":   Path("/tmp/edge_generator.json"),
    "data_freshness":   Path("/tmp/data_freshness.json"),
    "risk_alerts":      Path("/tmp/risk_alerts.json"),
    "intraday_signals": Path("/tmp/intraday_signals.json"),
}

DB_PATH = TRADING_DIR / "paper-trader" / "journal.db"
