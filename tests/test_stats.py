import numpy as np
import pytest

from qualgraph.data import PLANTED, make_fake_data
from qualgraph import stats
from qualgraph.matrices import build
from qualgraph.stats import cooccurrence, fdr_qvalues, min_attainable_q, permutation_pvalues

N_PERM = 200


def test_cooccurrence():
    M = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1]])
    C = cooccurrence(M)
    assert C[0, 1] == 2 and C[1, 2] == 2 and C[0, 2] == 1
    assert C[1, 1] == 3


def test_by_qvalues_hand_computed():
    p = np.array([0.01, 0.04, 0.03, 0.5])
    c = 1 + 1 / 2 + 1 / 3 + 1 / 4
    # Sorted p: .01 .03 .04 .5 -> raw p*m*c/rank, then step-up cumulative min.
    raw = np.array([0.01 * 4 / 1, 0.03 * 4 / 2, 0.04 * 4 / 3, 0.5 * 4 / 4]) * c
    stepped = np.minimum(np.minimum.accumulate(raw[::-1])[::-1], 1)
    np.testing.assert_allclose(fdr_qvalues(p, "by"), stepped[[0, 2, 1, 3]])


def test_bh_qvalues_hand_computed():
    p = np.array([0.01, 0.04, 0.03, 0.5])
    raw = np.array([0.01 * 4 / 1, 0.03 * 4 / 2, 0.04 * 4 / 3, 0.5 * 4 / 4])
    stepped = np.minimum(np.minimum.accumulate(raw[::-1])[::-1], 1)
    np.testing.assert_allclose(fdr_qvalues(p, "bh"), stepped[[0, 2, 1, 3]])


def test_min_attainable_q():
    m, n = 100, 9999
    c = np.sum(1 / np.arange(1, m + 1))
    assert min_attainable_q(m, n, "by") == pytest.approx(m * c / (n + 1))
    assert min_attainable_q(m, n, "bh") == pytest.approx(m / (n + 1))


@pytest.fixture(scope="module")
def planted():
    inc = build(make_fake_data(0))
    out = {}
    for mode, M, blocks in [("quote", inc.Q, inc.qp), ("participant", inc.P, None)]:
        i, j, count, p = permutation_pvalues(M, N_PERM, seed=0, blocks=blocks)
        out[mode] = {(inc.codes[a], inc.codes[b]): pv for a, b, pv in zip(i, j, p)}
    return out


def test_planted_quote_pair(planted):
    assert planted["quote"][PLANTED["quote_pair"]] == 1 / (N_PERM + 1)


def test_planted_participant_pair(planted):
    a, b = PLANTED["participant_pair"]
    assert planted["participant"][(a, b)] < 0.01
    # Never on the same quote, so no quote-level evidence at all.
    assert planted["quote"][(a, b)] == 1


def test_planted_pairs_rank_at_top(planted):
    for mode, key in [("quote", "quote_pair"), ("participant", "participant_pair")]:
        p = np.array(list(planted[mode].values()))
        assert np.mean(p <= planted[mode][PLANTED[key]]) < 0.05, mode


def test_calibration_without_structure():
    inc = build(make_fake_data(1, structured=False))
    for M, blocks in [(inc.Q, inc.qp), (inc.P, None)]:
        *_, p = permutation_pvalues(M, N_PERM, seed=1, blocks=blocks)
        # Discrete one-sided p-values are conservative: false-positive rate at
        # most a little over nominal.
        for alpha in (0.05, 0.2):
            assert np.mean(p < alpha) < alpha * 1.5


def test_parallel_chains_deterministic(monkeypatch):
    monkeypatch.setattr(stats, "CHUNK", 50)  # 2 chunks of 50, 1 of 20
    inc = build(make_fake_data(0))
    serial = permutation_pvalues(inc.P, 120, seed=3, workers=1)[3]
    parallel = permutation_pvalues(inc.P, 120, seed=3, workers=2)[3]
    np.testing.assert_array_equal(serial, parallel)


def test_npmi():
    n = 100
    # count, n_a, n_b: independent, always together, never together, and
    # 10 of 20 x 20 -> ln(10*100/400) / -ln(10/100).
    got = stats.npmi([4, 100, 0, 10], [20, 100, 30, 20], [20, 100, 30, 20], n)
    np.testing.assert_allclose(got, [0, 1, -1, np.log(2.5) / np.log(10)], atol=1e-12)


def test_compute_pairs_have_both_units():
    from qualgraph.build import compute

    data = compute(make_fake_data(0), N_PERM, 0, progress=lambda *a: None)
    assert len(data["pairs"]) == data["units"]["quote"]["n_tests"]
    for pair in data["pairs"]:
        for unit in ("quote", "participant"):
            s = pair[unit]
            assert -1 <= s["npmi"] <= 1 and 0 < s["p"] <= 1
            assert (s["count"] == 0) == (s["npmi"] == -1)
            assert s["q_bh"] <= s["q_by"]
