"""Rotinas numericas de apoio: suavizacao, deteccao de picos e integracao."""

from __future__ import annotations

from dataclasses import dataclass

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


# Piso de ruido. Em XICs de baixa contagem o ruido medido e exatamente zero
# (a maioria dos pontos vale 0), o que tornaria toda relacao sinal/ruido
# infinita e faria qualquer respingo de um unico count passar pelo filtro de
# picos. Um count e o menor ruido fisicamente possivel nesses dados.
NOISE_FLOOR = 1.0


def signal_to_noise(x: np.ndarray, y: np.ndarray, x0: float, x1: float,
                    noise_floor: float = NOISE_FLOOR) -> float:
    """Razao sinal/ruido grosseira: altura do pico sobre o desvio fora da faixa."""
    lo, hi = sorted((float(x0), float(x1)))
    inside = (x >= lo) & (x <= hi)
    outside = ~inside
    if inside.sum() == 0 or outside.sum() < 5:
        return 0.0
    noise = max(float(np.std(y[outside])), noise_floor)
    return float((y[inside].max() - np.median(y[outside])) / noise)


def gaussian_kernel(sigma: float) -> np.ndarray:
    """Kernel gaussiano normalizado, com largura de +-3 sigma."""
    radius = max(int(round(3.0 * sigma)), 1)
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (offsets / sigma) ** 2)
    return kernel / kernel.sum()


def gaussian_smooth(y: np.ndarray, sigma: float) -> np.ndarray:
    """
    Suavizacao gaussiana com `sigma` em pontos. Equivale ao Gaussian Smooth do
    PeakView e e o filtro certo para cromatogramas: preserva a posicao e a area
    do pico, ao contrario da media movel retangular.
    """
    if sigma <= 0 or y.size < 3:
        return y
    kernel = gaussian_kernel(sigma)
    radius = kernel.size // 2
    padded = np.pad(y, radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def rolling_minimum(y: np.ndarray, window: int) -> np.ndarray:
    """
    Envoltoria inferior de `y`, em O(n): minimo por blocos de `window` pontos,
    interpolado linearmente entre os centros dos blocos.
    """
    n = y.size
    window = int(np.clip(window, 2, max(n, 2)))
    if n < 3:
        return y.copy()
    edges = np.arange(0, n, window)
    centres, minima = [], []
    for start in edges:
        stop = min(start + window, n)
        if stop - start <= 0:
            continue
        centres.append((start + stop - 1) / 2.0)
        minima.append(float(y[start:stop].min()))
    if len(centres) < 2:
        return np.full(n, min(minima) if minima else 0.0)
    return np.interp(np.arange(n, dtype=np.float64), np.array(centres),
                     np.array(minima))


def subtract_baseline(x: np.ndarray, y: np.ndarray,
                      window: float = 1.0) -> np.ndarray:
    """
    Subtrai a linha de base de um cromatograma. `window` e a largura, nas
    unidades de `x` (minutos), usada para estimar a envoltoria inferior: deve
    ser maior que o pico mais largo que se quer preservar.
    """
    if y.size < 3 or x.size != y.size:
        return y
    span = float(x[-1] - x[0])
    if span <= 0:
        return y
    points = max(int(round(window / span * y.size)), 2)
    baseline = rolling_minimum(y, points)
    baseline = gaussian_smooth(baseline, max(points / 4.0, 1.0))
    return y - baseline


def estimate_noise(y: np.ndarray) -> float:
    """
    Ruido robusto pelo desvio absoluto mediano das diferencas ponto a ponto,
    escalado para equivaler a um desvio padrao. Insensivel a picos.

    Em XICs de baixa contagem o sinal e quantizado e mais da metade das
    diferencas e exatamente zero, o que zera o MAD. Nesse caso o ruido e
    estimado pelo desvio padrao da metade inferior dos pontos, que quase nunca
    contem pico. Devolver zero faria toda relacao sinal/ruido virar infinito e
    o filtro de picos deixaria passar qualquer coisa.
    """
    if y.size < 3:
        return 0.0
    diffs = np.diff(y)
    mad = float(np.median(np.abs(diffs - np.median(diffs))))
    if mad > 0:
        return mad * 1.4826 / np.sqrt(2.0)
    lower_half = np.sort(y)[: max(y.size // 2, 3)]
    return float(np.std(lower_half))


@dataclass(frozen=True)
class ChromPeak:
    """Pico cromatografico integrado."""

    apex_rt: float
    apex_index: int
    start_rt: float
    end_rt: float
    height: float
    area: float
    width: float
    snr: float


def detect_peaks(x: np.ndarray, y: np.ndarray, min_relative: float = 0.02,
                 min_snr: float = 3.0, smooth_sigma: float = 1.0,
                 max_peaks: int = 50,
                 noise_floor: float = NOISE_FLOOR) -> list[ChromPeak]:
    """
    Detecta e integra picos de um cromatograma.

    Cada apice e expandido para os dois lados ate o vale mais proximo (ou ate a
    inclinacao inverter), a linha de base e a reta que liga as bordas, e a area
    e integrada acima dela. `min_relative` e a altura minima em fracao do maior
    pico; `min_snr` descarta picos indistinguiveis do ruido.
    """
    if x.size != y.size or y.size < 5:
        return []
    smoothed = gaussian_smooth(y, smooth_sigma) if smooth_sigma > 0 else y
    if float(smoothed.max()) <= 0:
        return []

    noise = max(estimate_noise(y), noise_floor)
    threshold = float(smoothed.max()) * min_relative
    apexes = local_maxima(smoothed)
    apexes = apexes[smoothed[apexes] >= threshold]
    if apexes.size == 0:
        return []
    apexes = apexes[np.argsort(smoothed[apexes])[::-1][:max_peaks]]

    peaks: list[ChromPeak] = []
    for apex in apexes:
        apex = int(apex)
        left = apex
        while left > 0 and smoothed[left - 1] <= smoothed[left]:
            left -= 1
        right = apex
        while right < smoothed.size - 1 and smoothed[right + 1] <= smoothed[right]:
            right += 1
        if right - left < 2:
            continue
        xs, ys = x[left:right + 1], y[left:right + 1]
        baseline = np.linspace(ys[0], ys[-1], xs.size)
        corrected = np.clip(ys - baseline, 0.0, None)
        height = float(corrected.max())
        if height <= 0:
            continue
        snr = float(height / noise)
        if snr < min_snr:
            continue
        half = corrected >= height / 2.0
        width = float(xs[half][-1] - xs[half][0]) if half.any() else 0.0
        peaks.append(
            ChromPeak(
                apex_rt=float(x[apex]),
                apex_index=apex,
                start_rt=float(xs[0]),
                end_rt=float(xs[-1]),
                height=height,
                area=float(np.trapezoid(corrected, xs)),
                width=width,
                snr=snr,
            )
        )
    return sorted(peaks, key=lambda p: p.area, reverse=True)
