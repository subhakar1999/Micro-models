from micro_models.memory import Memory


def test_replacement_and_hostile_query(tmp_path):
    store = Memory(tmp_path / "memory.sqlite")
    store.ingest("a", "doc", "old invoice terms")
    store.ingest("a", "doc", "new shipping terms")
    assert store.search("a", "invoice") == []
    assert store.search("a", 'shipping\" OR * --')[0]["source"] == "doc"
    assert store.search("a", "!!!") == []
    assert sum(len(r["text"]) for r in store.search("a", "shipping", budget=7)) <= 7
