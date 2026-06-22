#!/usr/bin/env python3
"""
Kalman Filter — Price smoothing for quant modules
===================================================
Simple steady-state Kalman filter that estimates the true price from noisy
OHLCV observations. Reduces false signals from random wicks and volatility
spikes before data reaches the 10 quant modules.

Design:
  - State: [price, trend] — 2D state vector
  - Observation: closing price (can extend to OHLC)
  - Steady-state: Kalman gain converges quickly, no per-tick recomputation
  - Input: numpy array of closing prices
  - Output: smoothed price series (same length)

Usage:
    from kalman_filter import kalman_smooth
    smoothed = kalman_smooth(closes)

Theory:
    The filter treats each new price as a noisy observation of a hidden
    true price that evolves with a local linear trend. The Kalman gain
    balances between trusting the observation (high measurement noise)
    and trusting the model prediction (high process noise).
"""

import numpy as np
from typing import Optional


def kalman_smooth(prices: np.ndarray,
                  process_noise: float = 1e-5,
                  measurement_noise: float = 1e-3,
                  initial_price: Optional[float] = None) -> np.ndarray:
    """
    Apply Kalman smoothing to a price series.
    
    Args:
        prices: 1D array of closing prices
        process_noise: How much the true price can change per step (default: 1e-5)
        measurement_noise: How noisy the observed price is (default: 1e-3)
        initial_price: Starting estimate (default: first observed price)
    
    Returns:
        Smoothed price series of same length as input.
        First element = initial_price if provided, else prices[0].
    
    The ratio process_noise/measurement_noise controls smoothing strength:
        - Higher ratio → more smoothing, more lag
        - Lower ratio → less smoothing, closer to raw prices
    Default values are tuned for daily crypto data (moderate smoothing).
    """
    n = len(prices)
    if n < 2:
        return prices.copy()
    
    # State: [price, trend]
    # State transition: price' = price + trend, trend' = trend
    F = np.array([[1.0, 1.0],
                  [0.0, 1.0]])
    
    # Observation: we only observe price, not trend
    H = np.array([[1.0, 0.0]])
    
    # Process noise covariance (how much state drifts)
    Q = np.eye(2) * process_noise
    
    # Measurement noise covariance
    R = np.array([[measurement_noise]])
    
    # Initial state
    p0 = initial_price if initial_price is not None else float(prices[0])
    x = np.array([p0, 0.0])  # [price, trend]
    P = np.eye(2) * 0.1      # Initial uncertainty
    
    smoothed = np.zeros(n)
    smoothed[0] = p0
    
    for i in range(1, n):
        # Predict
        x = F @ x
        P = F @ P @ F.T + Q
        
        # Update
        z = float(prices[i])
        y_residual = z - (H @ x)[0]  # innovation
        
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)  # Kalman gain
        K = K.flatten()
        
        x = x + K * y_residual
        P = (np.eye(2) - np.outer(K, H)) @ P
        
        smoothed[i] = x[0]
    
    return smoothed


def kalman_smooth_ohlc(opens: np.ndarray, highs: np.ndarray,
                       lows: np.ndarray, closes: np.ndarray,
                       **kwargs) -> np.ndarray:
    """
    Smooth using typical price (H+L+C)/3 for better noise rejection.
    Falls back to close-only if OHLC arrays are unavailable.
    """
    typical = (highs + lows + closes) / 3.0
    return kalman_smooth(typical, **kwargs)


# ── Test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick smoke test
    np.random.seed(42)
    true_price = 100 + np.cumsum(np.random.randn(200) * 0.5)
    noisy_price = true_price + np.random.randn(200) * 1.5
    smoothed = kalman_smooth(noisy_price)
    
    mse_raw = np.mean((noisy_price - true_price) ** 2)
    mse_smooth = np.mean((smoothed - true_price) ** 2)
    
    print(f"Kalman Filter Test:")
    print(f"  Raw MSE: {mse_raw:.4f}")
    print(f"  Smooth MSE: {mse_smooth:.4f}")
    print(f"  Improvement: {(1 - mse_smooth/mse_raw)*100:.1f}%")
