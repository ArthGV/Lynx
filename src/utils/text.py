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
