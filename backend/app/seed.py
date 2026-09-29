"""Idempotent seed of the DSA topic graph."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .graph import ensure_edge
from .models import Setting, Topic

TOPICS: dict[str, str] = {
    "Arrays": "Indexing, two pointers, prefix sums, in-place transforms",
    "Strings": "Parsing, pattern matching, two-pointer on text",
    "Hash Table": "Maps and sets, frequency counting, O(1) lookup patterns",
    "Linked List": "Pointer rewiring, fast/slow, reversal, merge",
    "Stack": "LIFO, monotonic stack, expression evaluation",
    "Queue": "FIFO, deque, sliding structures",
    "Sorting": "Comparison sorts, custom order, sort-then-scan",
    "Binary Search": "Sorted search space, search-on-answer",
    "Sliding Window": "Fixed and variable windows over arrays/strings",
    "Two Pointers": "Opposite or same-direction scans",
    "Recursion": "Base cases, call stack, divide and conquer",
    "Backtracking": "Constraint search, permutations, pruning",
    "Trees": "Binary trees, BST, traversals",
    "Heap": "Priority queues, top-K, scheduling",
    "Graphs": "BFS, DFS, shortest paths, topo sort",
    "Union Find": "Disjoint sets, connectivity",
    "Trie": "Prefix trees, autocomplete, word search",
    "Greedy": "Local choices, interval scheduling, exchange args",
    "Dynamic Programming": "Memoization, tabulation, state design",
    "Bit Manipulation": "Bitmasks, XOR tricks, subset enumeration",
    "Math": "Number theory, combinatorics, modular arithmetic",
}

# (prerequisite, dependent)
EDGES: list[tuple[str, str]] = [
    ("Arrays", "Two Pointers"),
    ("Arrays", "Sliding Window"),
    ("Arrays", "Binary Search"),
    ("Arrays", "Sorting"),
    ("Strings", "Sliding Window"),
    ("Strings", "Trie"),
    ("Linked List", "Stack"),
    ("Recursion", "Backtracking"),
    ("Recursion", "Trees"),
    ("Recursion", "Dynamic Programming"),
    ("Trees", "Graphs"),
    ("Trees", "Heap"),
    ("Trees", "Trie"),
    ("Graphs", "Union Find"),
    ("Graphs", "Dynamic Programming"),
    ("Binary Search", "Heap"),
    ("Hash Table", "Graphs"),
    ("Sorting", "Greedy"),
    ("Stack", "Graphs"),
]


def seed_defaults(db: Session) -> None:
    by_name: dict[str, Topic] = {t.name: t for t in db.query(Topic).all()}
    changed = False
    for name, desc in TOPICS.items():
        if name not in by_name:
            t = Topic(name=name, description=desc)
            db.add(t)
            by_name[name] = t
            changed = True
    if changed:
        db.flush()

    for a, b in EDGES:
        if a in by_name and b in by_name:
            ensure_edge(db, by_name[a], by_name[b])

    if not db.get(Setting, "onboarded"):
        db.add(Setting(key="onboarded", value="false"))
    if not db.get(Setting, "daily_goal"):
        db.add(Setting(key="daily_goal", value="10"))

    db.commit()
