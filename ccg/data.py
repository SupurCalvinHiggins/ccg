"""Input data. Each record is one quote: (participant_id, [codes])."""

import csv
import io

import numpy as np

Record = tuple[str, list[str]]

# Ground truth planted by make_fake_data, used by tests.
PLANTED = {
    "quote_pair": ("code_00", "code_01"),        # co-tagged on the same quotes
    "participant_pair": ("code_02", "code_03"),  # same people, never the same quote
}

N_CODES = 100
THEMES = [list(range(10 + 8 * t, 18 + 8 * t)) for t in range(5)]  # codes 10..49


def load_data(path) -> list[Record]:
    """Read a CSV with header `participant,codes`; codes are `|`-separated."""
    with open(path, newline="") as f:
        return read_records(f)


def parse_data(text: str) -> list[Record]:
    """Same as load_data, from CSV text already in memory."""
    return read_records(io.StringIO(text, newline=""))


def read_records(f) -> list[Record]:
    reader = csv.DictReader(f)
    missing = {"participant", "codes"} - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV header must include participant,codes (missing: {', '.join(sorted(missing))})")
    return [(row["participant"], row["codes"].split("|")) for row in reader]


def make_fake_data(seed: int = 0, structured: bool = True) -> list[Record]:
    """~40 participants, 100 codes, ~1.5K quotes with planted structure.

    With structured=False every code is drawn independently by frequency,
    which gives a no-signal dataset for calibration checks.
    """
    rng = np.random.default_rng(seed)
    names = [f"code_{i:02d}" for i in range(N_CODES)]
    zipf = 1.0 / np.arange(1, N_CODES + 1) ** 0.8
    background = np.arange(4, N_CODES)
    bg_w = zipf[: len(background)] / zipf[: len(background)].sum()
    all_w = zipf / zipf.sum()

    n_people = 40
    group = set(rng.choice(n_people, size=10, replace=False))  # participant-level signal
    records = []
    for p in range(n_people):
        pid = f"P{p:02d}"
        for _ in range(rng.integers(15, 61)):
            k = rng.choice([1, 2, 3, 4], p=[0.3, 0.35, 0.25, 0.1])
            if not structured:
                codes = set(rng.choice(N_CODES, size=k, replace=False, p=all_w))
            else:
                if rng.random() < 0.5:
                    theme = THEMES[rng.integers(len(THEMES))]
                    codes = set(rng.choice(theme, size=k, replace=False))
                else:
                    codes = set(rng.choice(background, size=k, replace=False, p=bg_w))
                if rng.random() < 0.05:
                    codes.add(0)
                    if rng.random() < 0.7:
                        codes.add(1)
                elif rng.random() < 0.02:
                    codes.add(1)
                if rng.random() < (0.08 if p in group else 0.001):
                    codes.add(2 if rng.random() < 0.5 else 3)
            records.append((pid, [names[c] for c in sorted(codes)]))
    return records
