"""Rotinas numericas de apoio: suavizacao, deteccao de picos e integracao."""

from __future__ import annotations

import numpy as np


def moving_average(y: np.ndarray, window: int) -> np.ndarray:
    """Media movel centrada; `window` <= 1 devolve o vetor original."""
    if window <= 1 or y.size < window:
        return y
    kernel = np.ones(window, dtype=np.float64) / window
    padded = np.pad(y, (window // 2, window - 1 - window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def local_maxima(y: np.ndarray) -> np.ndarray:
    """Indices dos maximos locais (estritos a esquerda, nao estritos a direita)."""
    if y.size < 3:
        return np.zeros(0, dtype=int)
    return np.nonzero((y[1:-1] > y[:-2]) & (y[1:-1] >= y[2:]))[0] + 1


def centroid_mz(mz: np.ndarray, intensity: np.ndarray, apex: int,
                span: int = 2) -> float:
    """
    Refina a massa de um pico em dados de perfil pelo centro de gravidade
    dos pontos vizinhos ao apice.
    """
    lo = max(apex - span, 0)
    hi = min(apex + span + 1, mz.size)
    weights = intensity[lo:hi]
    total = weights.sum()
    if total <= 0:
        return float(mz[apex])
    return float((mz[lo:hi] * weights).sum() / total)


def pick_peaks(mz: np.ndarray, intensity: np.ndarray, max_peaks: int = 15,
               min_relative: float = 0.01, centroid: bool = True,
               min_distance: float = 0.03) -> list[tuple[float, float]]:
    """
    Lista de (m/z, intensidade) dos picos mais intensos, do maior para o menor.

    `min_relative` e a fracao da altura do pico base abaixo da qual os picos sao
    descartados. `min_distance` (em Da) funde maximos locais vizinhos: em dados
    de perfil o topo de um mesmo pico costuma render varios maximos, que de
    outro modo apareceriam como massas repetidas.
    """
    if mz.size == 0 or intensity.size == 0:
        return []
    idx = local_maxima(intensity)
    if idx.size == 0:
        idx = np.array([int(intensity.argmax())])
    threshold = intensity.max() * min_relative
    idx = idx[intensity[idx] >= threshold]
    if idx.size == 0:
        return []
    # do mais intenso para o menos intenso, descartando vizinhos muito proximos
    order = idx[np.argsort(intensity[idx])[::-1]]
    peaks: list[tuple[float, float]] = []
    for i in order:
        m = centroid_mz(mz, intensity, int(i)) if centroid else float(mz[i])
        if any(abs(m - kept) < min_distance for kept, _ in peaks):
            continue
        peaks.append((m, float(intensity[i])))
        if len(peaks) >= max_peaks:
            break
    return peaks


def integrate(x: np.ndarray, y: np.ndarray, x0: float, x1: float) -> dict:
    """
    Integra a faixa [x0, x1] de um cromatograma subtraindo uma linha de base
    reta entre os extremos da selecao.
    """
    lo, hi = sorted((float(x0), float(x1)))
    mask = (x >= lo) & (x <= hi)
    if mask.sum() < 2:
        return {"area": 0.0, "height": 0.0, "apex_rt": 0.0, "n_points": int(mask.sum())}
    xs, ys = x[mask], y[mask]
    baseline = np.linspace(ys[0], ys[-1], xs.size)
    corrected = np.clip(ys - baseline, 0, None)
    apex = int(corrected.argmax())
    return {
        "area": float(np.trapezoid(corrected, xs)),
        "height": float(corrected[apex]),
        "apex_rt": float(xs[apex]),
        "n_points": int(xs.size),
    }


def signal_to_noise(x: np.ndarray, y: np.ndarray, x0: float, x1: float) -> float:
    """Razao sinal/ruido grosseira: altura do pico sobre o desvio fora da faixa."""
    lo, hi = sorted((float(x0), float(x1)))
    inside = (x >= lo) & (x <= hi)
    outside = ~inside
    if inside.sum() == 0 or outside.sum() < 5:
        return 0.0
    noise = float(np.std(y[outside]))
    if noise <= 0:
        return 0.0
    return float((y[inside].max() - np.median(y[outside])) / noise)
