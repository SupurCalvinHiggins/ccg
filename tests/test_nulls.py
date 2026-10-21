import itertools

import numpy as np
from scipy.stats import chisquare

from qualgraph.data import make_fake_data
from qualgraph.matrices import build
from qualgraph.nulls import Curveball


def test_curveball_preserves_margins_and_blocks():
    inc = build(make_fake_data(0))
    for M, blocks in [(inc.Q, inc.qp), (inc.P, None)]:
        chain = Curveball(M, blocks)
        out = chain.shuffled(5 * len(M), seed=7)
        np.testing.assert_array_equal(out.sum(0), M.sum(0))
        np.testing.assert_array_equal(out.sum(1), M.sum(1))  # also rules out duplicates
        assert not np.array_equal(out, M)
        np.testing.assert_array_equal(chain.shuffled(5 * len(M), seed=7), out)
    out = Curveball(inc.Q, inc.qp).shuffled(5 * len(inc.Q), seed=8)
    P2 = np.zeros_like(inc.P)
    np.maximum.at(P2, inc.qp, out)
    np.testing.assert_array_equal(P2, inc.P)


def _all_matrices(M, blocks):
    """Every 0/1 matrix with M's row sums and per-block column sums."""
    out = []
    for bits in itertools.product([0, 1], repeat=M.size):
        X = np.array(bits, dtype=np.int8).reshape(M.shape)
        if (X.sum(1) == M.sum(1)).all() and all(
            (X[blocks == b].sum(0) == M[blocks == b].sum(0)).all() for b in np.unique(blocks)
        ):
            out.append(X.tobytes())
    return out


def test_curveball_samples_uniformly():
    M = np.array([[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 1, 1], [1, 0, 0, 1]], dtype=np.int8)
    for blocks in [np.zeros(4, int), np.array([0, 0, 1, 1])]:
        support = _all_matrices(M, blocks)
        chain = Curveball(M, blocks)
        draws = [chain.shuffled(50, seed=s).tobytes() for s in range(40 * len(support))]
        assert set(draws) <= set(support)
        counts = [draws.count(x) for x in support]
        assert chisquare(counts).pvalue > 0.001
