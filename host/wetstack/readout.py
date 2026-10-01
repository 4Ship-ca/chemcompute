"""Readout and statistics used by the gates."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import curve_fit
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score, permutation_test_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def linear_classifier():
    return make_pipeline(StandardScaler(), LogisticRegression(C=10.0, max_iter=5000))


def cv_accuracy(X: np.ndarray, y: np.ndarray, folds: int = 5, seed: int = 0) -> float:
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    return float(np.mean(cross_val_score(linear_classifier(), X, y, cv=cv)))


def permutation_p(X: np.ndarray, y: np.ndarray, n_perm: int = 1000, folds: int = 5, seed: int = 0) -> float:
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    _, _, p = permutation_test_score(linear_classifier(), X, y, cv=cv, n_permutations=n_perm,
                                     random_state=seed, n_jobs=1)
    return float(p)


def r_squared(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return (1 - ss_res / ss_tot if ss_tot > 0 else 0.0, float(slope), float(intercept))


def cv_pct(values) -> float:
    v = np.asarray(values, dtype=float)
    return float(np.std(v, ddof=1) / abs(np.mean(v)) * 100) if v.size > 1 and np.mean(v) != 0 else 0.0


def sigmoid(q, q50, width, top, bottom):
    # width = 10%-90% span; logistic slope k = ln(81) / width
    k = math.log(81.0) / max(width, 1e-9)
    return bottom + (top - bottom) / (1.0 + np.exp(-k * (q - q50)))


def fit_threshold(q: np.ndarray, y: np.ndarray) -> dict:
    q, y = np.asarray(q, float), np.asarray(y, float)
    q50_guess = float(q[np.argmin(np.abs(y - 0.5 * (y.max() + y.min())))])
    p0 = [max(q50_guess, 1e-3), max(q50_guess * 0.6, 1.0), float(y.max()), float(y.min())]
    popt, _ = curve_fit(sigmoid, q, y, p0=p0, maxfev=20000)
    pred = sigmoid(q, *popt)
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {"q50": float(popt[0]), "width": abs(float(popt[1])), "top": float(popt[2]), "bottom": float(popt[3]),
            "r2": 1 - ss_res / ss_tot if ss_tot > 0 else 0.0}


def fired_fraction(a_red: float, a_red_base: float, a_red_acid: float) -> float:
    """0 = baseline (blue, unfired), 1 = fully acid (yellow, fired), from red-channel absorbance."""
    span = a_red_base - a_red_acid
    return float((a_red_base - a_red) / span) if span != 0 else 0.0
