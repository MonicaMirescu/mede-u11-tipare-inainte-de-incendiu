"""Trustworthiness și vecinătăți euclidiene cu egalități departajate calendaristic."""
import numpy as np
from scipy.spatial.distance import cdist

from .io import require


def neighbors(values, k):
    values = np.asarray(values, dtype=float)
    require(np.isfinite(values).all(), "Valori nefinite în calculul vecinătăților")
    require(0 < k < len(values), "k invalid")
    distance = cdist(values, values, metric="euclidean")
    np.fill_diagonal(distance, np.inf)
    # Indexul rândului este ordinea datei. Nu se adaugă zgomot datelor repetate.
    return np.argsort(distance, axis=1, kind="stable")[:, :k]


def neighborhood_overlap(left, right):
    left, right = np.asarray(left), np.asarray(right)
    require(left.shape == right.shape and left.ndim == 2, "Vecinătăți nealiniate")
    return float((left[:, :, None] == right[:, None, :]).any(axis=2).mean())


class NeighborhoodReference:
    def __init__(self, original, k):
        original = np.asarray(original, dtype=float)
        self.n, self.k = len(original), k
        require(np.isfinite(original).all() and 0 < k < self.n / 2, "Trustworthiness necesită valori finite și k<n/2")
        distance = cdist(original, original, metric="euclidean")
        np.fill_diagonal(distance, np.inf)
        order = np.argsort(distance, axis=1, kind="stable")
        self.high_neighbors = order[:, :k]
        self.ranks = np.empty((self.n, self.n), dtype=np.int32)
        self.ranks[np.arange(self.n)[:, None], order] = np.arange(1, self.n + 1)

    def evaluate(self, projection):
        low = neighbors(projection, self.k)
        penalty = np.maximum(self.ranks[np.arange(self.n)[:, None], low] - self.k, 0).sum()
        trust = 1 - 2 * penalty / (self.n * self.k * (2 * self.n - 3 * self.k - 1))
        require(0 <= trust <= 1, "Trustworthiness în afara intervalului")
        return {"trustworthiness": float(trust),
                "knn_retention": neighborhood_overlap(self.high_neighbors, low)}, low
