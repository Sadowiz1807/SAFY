from __future__ import annotations

from pathlib import Path

from DataStore.schema_graph_store import SchemaGraphStore, build_schema_graph


def test_schema_graph_paths_do_not_collide_after_sanitization(tmp_path: Path) -> None:
    store = SchemaGraphStore(tmp_path / "schema_graph")
    first = build_schema_graph({"tables": []}, {"profile_id": "team/db", "display_name": "One"})
    second = build_schema_graph({"tables": []}, {"profile_id": "team_db", "display_name": "Two"})

    store.save(first)
    store.save(second)

    assert store.get("team/db")["database_name"] == "One"
    assert store.get("team_db")["database_name"] == "Two"
    assert len(list((tmp_path / "schema_graph" / "schemas").glob("*.schema_graph.json"))) == 2


def test_schema_graph_filename_is_bounded_for_long_profile_id(tmp_path: Path) -> None:
    store = SchemaGraphStore(tmp_path / "schema_graph")
    profile_id = "x" * 500
    store.save(build_schema_graph({"tables": []}, {"profile_id": profile_id, "display_name": "Long"}))

    paths = list((tmp_path / "schema_graph" / "schemas").glob("*.schema_graph.json"))
    assert len(paths) == 1
    assert len(paths[0].name) < 128
    assert store.get(profile_id)["database_name"] == "Long"
