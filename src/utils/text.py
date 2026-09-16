from typing import Any


def compare_raw(a: Any, b: Any) -> int:
    if a == b:
        return 0
    return 1 if a > b else -1


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + cost))
            row_min = min(row_min, current[-1])
        if row_min > 1:
            return row_min
        previous = current
    return previous[-1]


def edit_distance_seq(a: list[Any], b: list[Any], eq: Any) -> int:
    """Levenshtein distance between two sequences, using *eq(a, b)* for
    element equality.  An early exit bails as soon as the minimum is known
    to exceed 1 (the only threshold the callers care about)."""
    if a is b or a == b:
        return 0
    n = len(b)
    previous = list(range(n + 1))
    for i, xa in enumerate(a, 1):
        current = [i]
        row_min = i
        for j, xb in enumerate(b, 1):
            cost = 0 if eq(xa, xb) else 1
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + cost))
            row_min = min(row_min, current[-1])
        if row_min > 1:
            return row_min
        previous = current
    return previous[-1]


def edit_distance_sets(a: set[Any], b: set[Any]) -> int:
    """Minimum number of add / remove / rename edits that transform set *a*
    into set *b*.  Each rename converts one element; each add or remove
    touches one element.  `max(|a - b|, |b - a|)`."""
    return max(len(a - b), len(b - a))
