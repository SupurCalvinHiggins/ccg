"""Turn quote records into binary incidence matrices."""

from dataclasses import dataclass

import numpy as np

from .data import Record


@dataclass
class Incidence:
    codes: list[str]          # column labels
    participants: list[str]   # row labels of P
    Q: np.ndarray             # quotes x codes, 0/1
    P: np.ndarray             # participants x codes, 0/1
    qp: np.ndarray            # quote index -> participant index


def build(records: list[Record]) -> Incidence:
    codes = sorted({c for _, cs in records for c in cs})
    participants = sorted({p for p, _ in records})
    c_idx = {c: i for i, c in enumerate(codes)}
    p_idx = {p: i for i, p in enumerate(participants)}

    Q = np.zeros((len(records), len(codes)), dtype=np.int8)
    qp = np.empty(len(records), dtype=np.int64)
    for i, (p, cs) in enumerate(records):
        Q[i, [c_idx[c] for c in set(cs)]] = 1
        qp[i] = p_idx[p]

    P = np.zeros((len(participants), len(codes)), dtype=np.int8)
    np.maximum.at(P, qp, Q)
    return Incidence(codes, participants, Q, P, qp)
