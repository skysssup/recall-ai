from app.db import SessionLocal
from app.graph import ancestors, descendants, neighbors, serialize_graph, topological_layers
from app.models import Topic


def test_seeded_graph_has_layers():
    db = SessionLocal()
    try:
        layers = topological_layers(db)
        flat = [n for layer in layers for n in layer]
        assert "Arrays" in flat
        assert "Dynamic Programming" in flat
        # Arrays should appear in an earlier or equal layer than Sliding Window
        idx = {n: i for i, layer in enumerate(layers) for n in layer}
        assert idx["Arrays"] <= idx["Sliding Window"]
    finally:
        db.close()


def test_neighbors_arrays():
    db = SessionLocal()
    try:
        nbr = neighbors(db, "Arrays")
        assert "Sliding Window" in nbr["dependents"] or "Binary Search" in nbr["dependents"]
    finally:
        db.close()


def test_dp_ancestors_include_recursion():
    db = SessionLocal()
    try:
        anc = ancestors(db, "Dynamic Programming")
        assert "Recursion" in anc
    finally:
        db.close()


def test_serialize_graph():
    db = SessionLocal()
    try:
        g = serialize_graph(db)
        assert len(g["nodes"]) >= 15
        assert len(g["edges"]) >= 10
    finally:
        db.close()


def test_descendants_trees():
    db = SessionLocal()
    try:
        desc = descendants(db, "Trees")
        assert "Graphs" in desc or "Trie" in desc or "Heap" in desc
        assert db.query(Topic).count() > 0
    finally:
        db.close()
