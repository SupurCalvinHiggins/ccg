"""Co-occurrence counts, NPMI, permutation p-values and BH/BY FDR correction."""

from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.stats import false_discovery_control

from .nulls import Curveball


def cooccurrence(M: np.ndarray) -> np.ndarray:
    """Code x code co-occurrence counts (rows of M are the units)."""
    return M.T.astype(np.int64) @ M


def npmi(count, n_a, n_b, n: int) -> np.ndarray:
    """Normalised PMI of each pair: -1 never together, 0 independent, 1 always together.

    count, n_a, n_b are pair and per-code unit counts out of n units.
    """
    count, n_a, n_b = (np.asarray(x, dtype=float) for x in (count, n_a, n_b))
    out = np.where(count == 0, -1.0, 1.0)
    mid = (count > 0) & (count < n)
    c = count[mid]
    out[mid] = np.log(c * n / (n_a[mid] * n_b[mid])) / -np.log(c / n)
    return np.clip(out, -1, 1)  # rounding can step just outside


CHUNK = 10_000  # samples per independent chain


def _run_chunk(M, blocks, n, seed_seq, i, j, count):
    """Exceedance counts from one independent curveball chain of n samples."""
    seed = int(seed_seq.generate_state(1)[0])
    return Curveball(M, blocks).exceedances(n, seed, i, j, count)


def permutation_pvalues(M, n_perm, seed=0, blocks=None, workers=1, progress=None):
    """One-sided upper-tail p-values for every code pair i < j.

    All pairs are returned (unobserved ones get p = 1): FDR must be computed
    over all of them, since keeping only observed pairs selects on the outcome.
    The samples come from independent chains of CHUNK samples each, so results
    depend only on (seed, n_perm), not on the number of workers.
    Returns (i, j, count, p) arrays.
    """
    i, j = np.triu_indices(M.shape[1], k=1)
    count = cooccurrence(M)[i, j]

    sizes = [CHUNK] * (n_perm // CHUNK) + ([n_perm % CHUNK] if n_perm % CHUNK else [])
    seeds = np.random.SeedSequence(seed).spawn(len(sizes))
    exceed = np.zeros(len(i), dtype=np.int64)
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run_chunk, M, blocks, n, s, i, j, count) for n, s in zip(sizes, seeds)]
        for n, f in zip(sizes, futures):
            exceed += f.result()
            done += n
            if progress:
                progress(done, n_perm)
    p = (1 + exceed) / (1 + n_perm)
    return i, j, count, p


FDR_METHODS = ("bh", "by")


def fdr_qvalues(p, method: str) -> np.ndarray:
    """q-values over all tests in p: Benjamini-Hochberg ("bh") or Benjamini-Yekutieli
    ("by"). BY holds under any dependence between tests but costs a factor of
    ~ln(m) over BH."""
    return false_discovery_control(p, method=method)


def min_attainable_q(m: int, n_perm: int, method: str) -> float:
    """Smallest q a single top pair can reach given the permutation resolution."""
    p = np.ones(m)
    p[0] = 1 / (n_perm + 1)
    return float(fdr_qvalues(p, method)[0])
