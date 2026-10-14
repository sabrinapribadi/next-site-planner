"""P4 site-plan solvers (ADR-008).

Central model: each candidate hexagon j has a benefit b_j (expected people lifted above 25 Mbps) and a cost c_j
(new-tower equivalents); benefits do not overlap (P3: effects stay in the site's own hexagon), so the plan is a
0/1 knapsack, solved exactly with HiGHS. Sensitivity: rural macros also lift a fraction f of neighbouring hexagons
(3GPP radius), so benefits overlap and the plan is a budgeted maximal covering problem, solved greedily
(Khuller et al. 1999) and exactly where small enough.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix


def greedy_knapsack(b: np.ndarray, c: np.ndarray, budget: float) -> np.ndarray:
    """Pick by benefit ÷ cost until the budget is spent (skips items that no longer fit)."""
    order = np.argsort(-(b / c), kind="stable"); chosen = np.zeros(len(b), bool); spent = 0.0
    for j in order:
        if b[j] <= 0:
            break
        if spent + c[j] <= budget + 1e-9:
            chosen[j] = True; spent += c[j]
    return chosen


def exact_knapsack(b: np.ndarray, c: np.ndarray, budget: float, top: int = 20000, time_limit: float = 30, gap: float = 1e-4) -> tuple[np.ndarray, dict]:
    """0/1 knapsack (HiGHS) on the `top` candidates by benefit ÷ cost, solved to a proven relative gap of `gap`
    (0.01% by default; the achieved gap is reported). The rest cannot enter an optimal plan unless the top set is
    exhausted (checked)."""
    order = np.argsort(-(b / c), kind="stable")[:top]
    order = order[b[order] > 0]
    res = milp(c=-b[order], constraints=LinearConstraint(c[order][None, :], -np.inf, budget),
               integrality=np.ones(len(order)), bounds=Bounds(0, 1), options={"time_limit": time_limit, "mip_rel_gap": gap})
    chosen = np.zeros(len(b), bool)
    if res.x is not None:
        chosen[order[res.x > 0.5]] = True
    return chosen, {"status": int(res.status), "message": str(res.message), "candidates": int(len(order)),
                    "mip_gap": float(getattr(res, "mip_gap", float("nan")) or 0.0),
                    "budget_fits_in_top": bool(c[order].sum() > budget)}


def kpi_ranking(score: np.ndarray, c: np.ndarray, budget: float) -> np.ndarray:
    """The usual practice: rank by a composite KPI score and fill the budget in that order."""
    order = np.argsort(-score, kind="stable"); chosen = np.zeros(len(score), bool); spent = 0.0
    for j in order:
        if spent + c[j] <= budget + 1e-9:
            chosen[j] = True; spent += c[j]
        if spent >= budget - 1e-9:
            break
    return chosen


def zscore(x: np.ndarray) -> np.ndarray:
    s = np.nanstd(x)
    return np.nan_to_num((x - np.nanmean(x)) / (s if s > 0 else 1.0))


def greedy_cover(w: np.ndarray, cover: csr_matrix, c: np.ndarray, budget: float) -> np.ndarray:
    """Budgeted maximal covering with partial coverage: covered share of hexagon h = min(1, Σ_j f_jh x_j).
    cover[j, h] = f_jh. Greedy on marginal gain ÷ cost (lazy evaluation)."""
    n_c = cover.shape[0]; covered = np.zeros(cover.shape[1]); chosen = np.zeros(n_c, bool); spent = 0.0
    def gain(j):
        row = cover.getrow(j); idx, f = row.indices, row.data
        return float(np.sum(w[idx] * (np.minimum(1.0, covered[idx] + f) - covered[idx])))
    import heapq
    heap = [(-gain(j) / c[j], j) for j in range(n_c)]; heapq.heapify(heap)
    while heap:
        neg, j = heapq.heappop(heap)
        if chosen[j] or spent + c[j] > budget + 1e-9:
            continue
        g = gain(j) / c[j]
        if heap and g < -heap[0][0] - 1e-12:
            heapq.heappush(heap, (-g, j)); continue
        if g <= 0:
            break
        chosen[j] = True; spent += c[j]
        row = cover.getrow(j); covered[row.indices] = np.minimum(1.0, covered[row.indices] + row.data)
    return chosen


def cover_value(w: np.ndarray, cover: csr_matrix, chosen: np.ndarray) -> float:
    covered = np.minimum(1.0, np.asarray(cover[chosen].sum(axis=0)).ravel())
    return float(np.sum(w * covered))


def exact_cover(w: np.ndarray, cover: csr_matrix, c: np.ndarray, budget: float, time_limit: float = 120) -> tuple[np.ndarray, float]:
    """Exact budgeted maximal covering (small instances): max Σ w_h y_h, y_h ≤ Σ_j f_jh x_j, y_h ≤ 1, Σ c_j x_j ≤ B."""
    nj, nh = cover.shape
    obj = np.r_[np.zeros(nj), -w]
    A1 = np.hstack([-cover.T.toarray(), np.eye(nh)])               # y_h - Σ f_jh x_j ≤ 0
    A2 = np.r_[c, np.zeros(nh)][None, :]
    res = milp(c=obj, constraints=[LinearConstraint(A1, -np.inf, 0), LinearConstraint(A2, -np.inf, budget)],
               integrality=np.r_[np.ones(nj), np.zeros(nh)], bounds=Bounds(0, 1), options={"time_limit": time_limit})
    chosen = res.x[:nj] > 0.5 if res.x is not None else np.zeros(nj, bool)
    return chosen, (-res.fun if res.x is not None else float("nan"))
