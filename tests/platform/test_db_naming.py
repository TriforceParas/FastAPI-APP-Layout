"""Guards `.claude/skills/db-naming-conventions/SKILL.md` for every model."""

from __future__ import annotations

import re

from app.db.base import Base

# Table prefixes from section 2 of the convention (non-table objects excluded).
TABLE_PREFIXES = (
    "md_", "txn_", "map_", "cfg_",
    "log_", "aud_", "hist_", "arc_", "stg_", "tmp_",
    "dim_", "fact_", "agg_", "rpt_",
)  # fmt: skip
AUDITED_PREFIXES = ("md_", "txn_", "cfg_")  # need created/updated at/by
STANDARD_AUDIT_COLUMNS = {"created_at", "updated_at", "created_by", "updated_by"}
FORBIDDEN = re.compile(r"(^|_)(bkp|bak|old|new|copy|v\d+)(_|$)")


def tables():
    return Base.metadata.sorted_tables


def test_every_table_has_exactly_one_known_prefix():
    for table in tables():
        name = table.name
        assert re.fullmatch(r"[a-z][a-z0-9_]*", name), f"{name}: snake_case lowercase only"
        assert len(name) <= 63, f"{name}: longer than 63 characters"
        matches = [p for p in TABLE_PREFIXES if name.startswith(p)]
        assert len(matches) == 1, f"{name}: needs exactly one prefix from the convention"
        assert not any(name[len(matches[0]) :].startswith(p) for p in TABLE_PREFIXES), f"{name}: stacked prefixes"
        assert not FORBIDDEN.search(name), f"{name}: forbidden suffix/prefix"


def test_primary_key_is_id():
    for table in tables():
        assert [c.name for c in table.primary_key.columns] == ["id"], f"{table.name}: primary key must be `id`"


def test_foreign_keys_are_named_after_the_referenced_entity():
    for table in tables():
        for fk in table.foreign_keys:
            entity = fk.column.table.name.split("_", 1)[1]
            # `<entity>_id`, optionally qualified (parent_screen_id, default_screen_id)
            assert fk.parent.name.endswith(f"{entity}_id"), f"{table.name}.{fk.parent.name} should end with {entity}_id"


def test_audit_columns_on_md_txn_cfg_tables():
    for table in tables():
        if table.name.startswith(AUDITED_PREFIXES):
            missing = STANDARD_AUDIT_COLUMNS - {c.name for c in table.columns}
            assert not missing, f"{table.name} is missing audit columns: {sorted(missing)}"


def test_index_and_constraint_names():
    for table in tables():
        for index in table.indexes:
            prefix = "uq_" if index.unique else "idx_"
            assert index.name and index.name.startswith(f"{prefix}{table.name}_"), index.name
        for fk in table.foreign_key_constraints:
            assert fk.name == f"fk_{table.name}_{fk.column_keys[0]}", fk.name
        for constraint in table.constraints:
            if constraint.__class__.__name__ == "UniqueConstraint":
                assert constraint.name and constraint.name.startswith(f"uq_{table.name}_"), constraint.name
            if constraint.__class__.__name__ == "CheckConstraint":
                assert constraint.name and constraint.name.startswith(f"ck_{table.name}_"), constraint.name
