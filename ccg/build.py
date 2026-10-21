"""Compute co-occurrence statistics and write a self-contained HTML graph.

    python -m qualgraph.build --data quotes.csv --n-perm 1000000 --seed 0 --out graph.html

The CSV has one row per quote, with header `participant,codes`, codes separated by `|`:

    participant,codes
    P01,trust|communication
    P01,cost
"""

import argparse
import json
import os
from pathlib import Path

from .data import load_data, make_fake_data
from .matrices import build
from .stats import FDR_METHODS, fdr_qvalues, min_attainable_q, npmi, permutation_pvalues

WEB = Path(__file__).resolve().parent.parent / "web"


def print_progress(mode, done, total):
    print(f"  {mode}: {done}/{total}", flush=True)


def compute(records, n_perm: int, seed: int, progress=print_progress) -> dict:
    """progress(mode, done, total) is called after each chunk of permutations.

    Runs one worker process per CPU core available to this process.
    """
    workers = os.process_cpu_count() or 1
    inc = build(records)
    units, stats = {}, {}
    for k, (mode, M, blocks) in enumerate([("quote", inc.Q, inc.qp), ("participant", inc.P, None)]):
        print(f"{mode}: {n_perm} permutations on {workers} workers")
        i, j, count, p = permutation_pvalues(
            M, n_perm, seed=[seed, k], blocks=blocks, workers=workers,
            progress=lambda s, n: progress(mode, s, n),
        )
        q = {m: fdr_qvalues(p, m) for m in FDR_METHODS}
        q_floor = {m: min_attainable_q(len(p), n_perm, m) for m in FDR_METHODS}
        seen = count >= 1
        print(f"  {seen.sum()} observed of {len(p)} pairs; smallest attainable q for a lone top pair: "
              + ", ".join(f"{m.upper()} {v:.3g}" for m, v in q_floor.items()))
        marg = M.sum(axis=0)
        stats[mode] = (count, p, q["bh"], q["by"], npmi(count, marg[i], marg[j], M.shape[0]))
        units[mode] = {
            "n": M.shape[0],
            "n_tests": len(p),
            "n_perm": n_perm,
            "min_attainable_q": q_floor,
        }
    # Both units test the same pairs (i, j) in the same order. Every pair is
    # kept, including count 0 (p = q = 1, npmi = -1); the page only draws
    # pairs that co-occur in the unit it filters on.
    pairs = [{"a": int(a), "b": int(b)} for a, b in zip(i, j)]
    for mode, cols in stats.items():
        for pair, (c, pv, bh, by, nv) in zip(pairs, zip(*cols)):
            pair[mode] = {"count": int(c), "p": float(pv), "q_bh": float(bh), "q_by": float(by),
                          "npmi": float(nv)}
    codes = [
        {"id": c, "n_quotes": int(inc.Q[:, k].sum()), "n_participants": int(inc.P[:, k].sum())}
        for k, c in enumerate(inc.codes)
    ]
    meta = {"n_quotes": len(records), "n_participants": len(inc.participants), "seed": seed}
    return {"codes": codes, "pairs": pairs, "units": units, "meta": meta}


def render_html(data: dict | None) -> str:
    """With data=None the page starts empty and asks qualgraph.server for data."""
    template = (WEB / "template.html").read_text()
    app = (WEB / "app.js").read_text()
    payload = json.dumps(data).replace("</", "<\\/")
    return template.replace("/*__DATA__*/", payload).replace("/*__APP__*/", app)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", help="CSV with header participant,codes (default: fake data)")
    ap.add_argument("--n-perm", type=int, default=1_000_000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="graph.html")
    args = ap.parse_args()

    if args.data:
        records = load_data(args.data)
    else:
        print("no --data given; using fake data")
        records = make_fake_data(0)
    data = compute(records, args.n_perm, args.seed)
    data["meta"]["source"] = Path(args.data).name if args.data else "fake data"
    Path(args.out).write_text(render_html(data))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
