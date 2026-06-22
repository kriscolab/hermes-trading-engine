"""Crypto Engine Quant Layer — v12.0

13 quant modules with regime-gated activation:
  10 original: mean-reversion, momentum, correlation, stat-arbitrage, monte-carlo,
               volatility-arbitrage, ml-signals, event-driven, market-making, microstructure
  3 new (v12): orderflow, tape-reading, volume-profile

Plus: execution gate + risk manager integration.
"""

from .execution_gate import Gate, update_persistence, REGIME_MODULES
from .risk_manager import RiskManager
from .orderflow import orderflow_edge
from .tape_reading import tape_edge
from .volume_profile import volume_profile_edge

__all__ = [
    "Gate", "RiskManager", "update_persistence", "REGIME_MODULES",
    "orderflow_edge", "tape_edge", "volume_profile_edge",
]
