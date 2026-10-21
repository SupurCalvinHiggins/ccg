"""Curveball sampler for binary matrices with fixed row and column sums."""

import numpy as np
from numba import njit


# A trade picks two rows of the same block, pools the codes that are in only
# one of them, shuffles the pool and deals it back keeping row lengths. Rows
# live in one flat array `codes` with offsets `ptr` (row lengths never change),
# and rows of a block are contiguous so a block is just (start, size).


@njit(cache=True)
def _trade(codes, ptr, i, j, mark, buf):
    si, ei, sj, ej = ptr[i], ptr[i + 1], ptr[j], ptr[j + 1]
    # Row i: shared codes to the front, codes only in i to buf.
    for k in range(sj, ej):
        mark[codes[k]] = 1
    w_i, n_i = si, 0
    for k in range(si, ei):
        c = codes[k]
        if mark[c]:
            codes[w_i] = c
            w_i += 1
        else:
            buf[n_i] = c
            n_i += 1
    for k in range(sj, ej):
        mark[codes[k]] = 0
    # Row j: same, against row i's original codes (shared + buf[:n_i]).
    for k in range(si, w_i):
        mark[codes[k]] = 1
    for k in range(n_i):
        mark[buf[k]] = 1
    w_j, n = sj, n_i
    for k in range(sj, ej):
        c = codes[k]
        if mark[c]:
            codes[w_j] = c
            w_j += 1
        else:
            buf[n] = c
            n += 1
    for k in range(si, w_i):
        mark[codes[k]] = 0
    for k in range(n_i):
        mark[buf[k]] = 0
    # Shuffle the pooled non-shared codes and deal them back.
    for k in range(n - 1, 0, -1):
        r = np.random.randint(0, k + 1)
        buf[k], buf[r] = buf[r], buf[k]
    for k in range(n_i):
        codes[w_i + k] = buf[k]
    for k in range(n - n_i):
        codes[w_j + k] = buf[n_i + k]


@njit(cache=True)
def _sweep(codes, ptr, bstart, bsize, bcum, n_trades, mark, buf):
    for _ in range(n_trades):
        # Block chosen in proportion to its number of row pairs.
        g = min(np.searchsorted(bcum, np.random.random(), side="right"), len(bcum) - 1)
        s = bsize[g]
        a = np.random.randint(0, s)
        b = (a + 1 + np.random.randint(0, s - 1)) % s
        _trade(codes, ptr, bstart[g] + a, bstart[g] + b, mark, buf)


@njit(cache=True)
def _cooccurrence(codes, ptr, C):
    C[:] = 0
    for r in range(len(ptr) - 1):
        for x in range(ptr[r], ptr[r + 1]):
            for y in range(x + 1, ptr[r + 1]):
                a, b = codes[x], codes[y]
                if a > b:
                    a, b = b, a
                C[a, b] += 1


@njit(cache=True)
def _run_chain(codes, ptr, bstart, bsize, bcum, n_codes, n_samples, seed, ii, jj, obs):
    np.random.seed(seed)
    codes = codes.copy()
    mark = np.zeros(n_codes, np.int8)
    buf = np.empty(2 * n_codes, np.int32)
    C = np.zeros((n_codes, n_codes), np.int32)
    n_rows = len(ptr) - 1
    exceed = np.zeros(len(ii), np.int64)
    _sweep(codes, ptr, bstart, bsize, bcum, 5 * n_rows, mark, buf)  # burn-in
    for _ in range(n_samples):
        _sweep(codes, ptr, bstart, bsize, bcum, n_rows, mark, buf)
        _cooccurrence(codes, ptr, C)
        for k in range(len(ii)):
            if C[ii[k], jj[k]] >= obs[k]:
                exceed[k] += 1
    return exceed


@njit(cache=True)
def _shuffle(codes, ptr, bstart, bsize, bcum, n_codes, n_trades, seed):
    np.random.seed(seed)
    codes = codes.copy()
    _sweep(codes, ptr, bstart, bsize, bcum, n_trades,
           np.zeros(n_codes, np.int8), np.empty(2 * n_codes, np.int32))
    return codes


class Curveball:
    """Markov chain over 0/1 matrices with the same margins as M.

    With `blocks`, trades only happen between rows in the same block, so each
    block's column sums are also preserved (e.g. codes shuffled only among one
    participant's quotes).
    """

    def __init__(self, M: np.ndarray, blocks=None):
        n = M.shape[0]
        blocks = np.zeros(n, dtype=np.int64) if blocks is None else np.asarray(blocks)
        self.shape = M.shape
        self.order = np.argsort(blocks, kind="stable")
        rows = [np.flatnonzero(M[r]) for r in self.order]
        self.codes = np.concatenate(rows).astype(np.int32)
        self.ptr = np.concatenate([[0], np.cumsum([len(r) for r in rows])]).astype(np.int64)
        _, start, size = np.unique(blocks[self.order], return_index=True, return_counts=True)
        keep = size >= 2
        self.bstart, self.bsize = start[keep].astype(np.int64), size[keep].astype(np.int64)
        pairs = (self.bsize * (self.bsize - 1)).astype(float)
        self.bcum = np.cumsum(pairs) / pairs.sum()

    def exceedances(self, n_samples, seed, ii, jj, obs):
        """Per pair, how many of n_samples null draws have count >= obs."""
        return _run_chain(self.codes, self.ptr, self.bstart, self.bsize, self.bcum,
                          self.shape[1], n_samples, seed, ii, jj, obs)

    def shuffled(self, n_trades, seed) -> np.ndarray:
        """The 0/1 matrix after n_trades trades (rows in M's original order)."""
        codes = _shuffle(self.codes, self.ptr, self.bstart, self.bsize, self.bcum,
                         self.shape[1], n_trades, seed)
        M = np.zeros(self.shape, dtype=np.int8)
        for k, r in enumerate(self.order):
            M[r, codes[self.ptr[k]:self.ptr[k + 1]]] = 1
        return M
