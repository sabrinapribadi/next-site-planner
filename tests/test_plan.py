"""ADR-008 solvers: exact knapsack is optimal, greedy is close, KPI ranking can lose, covering respects overlaps."""

import itertools

import numpy as np
from scipy.sparse import csr_matrix

from src.plan import cover_value, exact_cover, exact_knapsack, greedy_cover, greedy_knapsack, kpi_ranking


def test_exact_knapsack_matches_brute_force():
    rng = np.random.default_rng(0)
    b = rng.random(14) * 10; c = rng.choice([0.3, 0.5, 1.0], 14); B = 3.0
    best = max(sum(b[list(s)]) for r in range(15) for s in itertools.combinations(range(14), r) if sum(c[list(s)]) <= B + 1e-9)
    chosen, info = exact_knapsack(b, c, B)
    assert abs(b[chosen].sum() - best) < 1e-6 and c[chosen].sum() <= B + 1e-9
    g = greedy_knapsack(b, c, B)
    assert b[g].sum() <= best + 1e-9 and b[g].sum() >= 0.6 * best


def test_kpi_ranking_can_miss_people():
    # KPI score favours very slow but nearly empty places; the optimiser favours many slow people
    b = np.array([1.0, 1.0, 50.0, 40.0]); c = np.ones(4); score = np.array([3.0, 2.5, 1.0, 0.5])
    assert b[kpi_ranking(score, c, 2)].sum() == 2.0 and b[exact_knapsack(b, c, 2)[0]].sum() == 90.0


def test_cover_counts_overlap_once():
    w = np.array([10.0, 10.0, 10.0])
    cover = csr_matrix(np.array([[1.0, 1.0, 0.0], [0.0, 1.0, 1.0], [0.0, 0.5, 0.0]]))
    c = np.array([1.0, 1.0, 0.3])
    ch = greedy_cover(w, cover, c, 2.0)
    assert cover_value(w, cover, ch) == 30.0
    ex, val = exact_cover(w, cover, c, 1.0)
    assert abs(val - 20.0) < 1e-6
