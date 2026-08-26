# Schema proposal: index on `designdb.poses (pose_alias, target_id)`

**Status:** proposed, not applied. The schema is not under HIPPO's control — this needs
the DB manager's approval. Nothing in HIPPO depends on it; it is a pure read-path
optimisation.

## The change

```sql
-- Non-unique btree. Safe to run on a live database: CONCURRENTLY avoids the
-- AccessExclusiveLock that a plain CREATE INDEX would hold on designdb.poses for
-- the duration of the build.
-- NOTE: CREATE INDEX CONCURRENTLY cannot run inside a transaction block, so this
-- must be executed as its own statement (not wrapped in BEGIN/COMMIT).
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pose_alias_target
    ON designdb.poses (pose_alias, target_id);
```

Rollback is symmetrical and equally non-blocking:

```sql
DROP INDEX CONCURRENTLY IF EXISTS designdb.idx_pose_alias_target;
```

Optional refinement — `pose_alias` is nullable and every query below filters it with
`=` or `IN` (which implies NOT NULL), so a partial index is still usable by the planner:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pose_alias_target
    ON designdb.poses (pose_alias, target_id)
    WHERE pose_alias IS NOT NULL;
```

Worth it only if a large share of rows have a NULL alias. Check with:

```sql
SELECT count(*) FILTER (WHERE pose_alias IS NULL) AS null_alias,
       count(*) AS total
FROM designdb.poses;
```

## Why it is necessary

`pose_alias` is currently **indexed nowhere**. In `init-db/01_schema.sql` it appears
exactly twice: the column declaration (line 82) and a unique constraint that was
deliberately commented out (line 99, `-- CONSTRAINT uc_pose_alias UNIQUE (pose_alias),
-- Removed`). The four indexes on `poses` (lines 484–487) cover `compound_id`,
`target_id`, `protein_link` and `created_on`.

Every lookup by alias is therefore a sequential scan of `poses`.

The queries that need it:

1. **`PoseService.resolve_aliases_batch`** (`services/pose.py:135`) —
   `WHERE pose_alias IN (...) AND target_id = ?`. The shared lookup behind both
   reference and inspiration resolution during SDF ingestion, so it runs on every load.

2. **`PoseService.create_batch`** (`services/pose.py:350`) —
   `WHERE target_id = ? AND compound_id IN (...) AND pose_alias IN (...)`. Runs once per
   ingested batch to find poses that already exist.

3. **Syndirella ingestion** (`services/ingestion.py:1110` and `:1136`) —
   `pose_alias__in=..., target=...` and `get(pose_alias=..., target=...)`.

4. **`PoseSet` bulk paths** — `sets/pose.py:1370` (`pose_alias__in=...`, **no target
   filter**), plus `:1676` and `:1690`, which filter on target and alias together.

Note on scale: SDF ingestion is now set-based, so these run a handful of times per load
rather than once per record. That lowers the urgency relative to the original analysis —
but each remains a full scan of `poses`, and at production row counts a handful of
sequential scans per load is still worth removing.

### Why `pose_alias` leads the index

Call site 4 (`sets/pose.py:1370`) filters on alias alone. A btree is only usable for a
leading-column prefix, so `(pose_alias, target_id)` serves both the alias-only lookups
and the alias+target ones. The reverse order, `(target_id, pose_alias)`, would serve only
the latter — its usable prefix, `target_id` alone, is already covered by the existing
`idx_pose_target_id`.

### Where it does *not* help

Lookups that also filter on `compound_id` are already served by the existing
`idx_pose_compound_id`, which is highly selective — few poses share a compound. The
lookups that genuinely fall back to a sequential scan are the ones where `compound_id` is
absent from the predicate: call sites 1, 3 and 4.

### What this does *not* do

It is **not** a unique index. The `uc_pose_alias` unique constraint was removed
deliberately and this proposal does not reinstate it — aliases stay non-unique, and no
existing row can be rejected by adding this.

## Cost

One additional btree over two text columns. Every insert into `poses`, and every update
touching `pose_alias` or `target_id`, pays one extra index maintenance. Ingestion is
insert-heavy, so this is a real cost, but a btree insert is negligible next to the work
already done per pose row (mol serialisation, the cartridge trigger
`trg_populate_pose_cartridge_from_mol`, and the round trip itself).

## How to verify it worked

Before and after, against production-sized data:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM designdb.poses
WHERE pose_alias = '<some alias>' AND target_id = <id>;
```

Expect `Seq Scan on poses` before and `Index Scan using idx_pose_alias_target` after, with
a large drop in `shared read`/`shared hit` buffer counts.

Confirm the planner actually chooses it after a real load:

```sql
SELECT indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE relname = 'poses';
```

`idx_scan` for `idx_pose_alias_target` should be non-zero and climbing.

## If accepted

Two places need to stay in sync:

- `images/xchem-designdb/init-db/01_schema.sql`, alongside the other pose indexes at
  lines 484–487. (This is the live schema — the Dockerfile does
  `COPY init-db/ /docker-entrypoint-initdb.d/`.)
- `PoseModel.Meta.indexes` in `hippo/designdb/models.py`, which mirrors those four
  indexes and drives SQLite mode. Note the existing comment just above it —
  `# although.. would alias-target combo work?` — this proposal is the answer to it.

```python
models.Index(fields=['pose_alias', 'target'], name='idx_pose_alias_target'),
```
