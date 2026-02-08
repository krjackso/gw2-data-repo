# Data Distribution Design

How to provide GW2 acquisition data to external consumers (TypeScript, Python, Rust, Go, etc.) efficiently.

## Problem

The raw data lives as individual YAML files (`data/items/{id}.yaml`) with separate name-index YAML files. This format works well for the populate/validate pipeline but is poor for external consumers:

- **Many small files**: ~1,500 YAML files at full scale, impractical to fetch individually
- **Large indexes**: The item name index is 50K+ entries (2MB YAML), slow to parse
- **No query support**: Consumers must load all files into memory and write their own lookup/traversal logic
- **No types**: Consumers have no generated types for their language — must hand-write interfaces from the JSON Schema

## Requirements

| Requirement | Detail |
|---|---|
| Languages | TypeScript first; Python, Rust, Go expected |
| Loading | Fetch a single artifact at startup from a URL (GitHub release) |
| Primary queries | Lookup by ID, lookup by name, follow requirement references |
| Size | Reasonable — server-side/desktop apps, not mobile |
| Updates | GitHub releases (tag-triggered) |
| Type safety | Auto-generate types/interfaces from the existing JSON Schema |

## Current Data at Scale

| Metric | Current (38 items) | Projected (1,500 items) |
|---|---|---|
| Item files | 160KB total | ~6.3MB |
| Acquisitions | ~146 | ~5,700 |
| Requirements | ~267 | ~10,300 |
| Name index | 50K names, 2MB | Same (covers full API) |
| Currency index | 78 entries | ~80 |

---

## Options

### Option A: SQLite Database File

Single `.sqlite` file with normalized relational tables.

**Schema:**
```sql
CREATE TABLE items (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL,
    rarity       TEXT NOT NULL,
    level        INTEGER NOT NULL,
    icon         TEXT,
    description  TEXT,
    vendor_value INTEGER,
    flags        TEXT,            -- JSON array
    wiki_url     TEXT,
    last_updated TEXT NOT NULL
);

CREATE TABLE acquisitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER NOT NULL REFERENCES items(id),
    type             TEXT NOT NULL,
    vendor_name      TEXT,
    output_quantity  INTEGER NOT NULL DEFAULT 1,
    metadata         TEXT,        -- JSON blob, type-specific
    sort_order       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE requirements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    acquisition_id  INTEGER NOT NULL REFERENCES acquisitions(id),
    item_id         INTEGER,
    currency_id     INTEGER,
    quantity        INTEGER NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    CHECK (item_id IS NOT NULL OR currency_id IS NOT NULL)
);

CREATE TABLE item_names (
    name    TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    PRIMARY KEY (name, item_id)
);

CREATE TABLE currency_names (
    name        TEXT NOT NULL PRIMARY KEY,
    currency_id INTEGER NOT NULL
);

CREATE INDEX idx_acq_item ON acquisitions(item_id);
CREATE INDEX idx_req_acq ON requirements(acquisition_id);
CREATE INDEX idx_req_item ON requirements(item_id);
CREATE INDEX idx_names ON item_names(name);
```

**Tree traversal is a single query:**
```sql
WITH RECURSIVE tree(item_id, depth) AS (
    SELECT :target_id, 0
    UNION ALL
    SELECT r.item_id, t.depth + 1
    FROM tree t
    JOIN acquisitions a ON a.item_id = t.item_id
    JOIN requirements r ON r.acquisition_id = a.id
    WHERE r.item_id IS NOT NULL AND t.depth < 10
)
SELECT DISTINCT i.* FROM tree t JOIN items i ON i.id = t.item_id;
```

| Criterion | Rating | Notes |
|---|---|---|
| Portability | Excellent | Libraries in every language |
| Query capability | Excellent | Full SQL, recursive CTEs |
| Size (compressed) | ~1MB | 3-5MB raw, compresses well |
| Maintenance | Low | One build script |
| Type safety | Moderate | No built-in types; metadata is a JSON blob |
| Ecosystem | Excellent | `better-sqlite3`, `sqlite3` stdlib, `rusqlite`, `modernc.org/sqlite` |

**Pros:** Single file, SQL queries, indexed tree traversal, no serialization overhead, atomic updates.

**Cons:** Metadata as JSON blob loses type safety at the SQL level. Binary format — not human-readable. Consumers need SQLite as a dependency.

---

### Option B: Single JSON Bundle

All data serialized into one JSON file.

```json
{
  "version": "1.0.0",
  "generatedAt": "2026-02-07",
  "items": {
    "19676": { "name": "Icy Runestone", "type": "Trophy", "acquisitions": [...] }
  },
  "nameIndex": { "Icy Runestone": [19676] },
  "currencyIndex": { "Coin": 1, "Karma": 2 }
}
```

| Criterion | Rating | Notes |
|---|---|---|
| Portability | Excellent | JSON is universal |
| Query capability | Poor | Linear scans, manual index building |
| Size (compressed) | ~1.5MB | 5-8MB raw |
| Maintenance | Very low | Serialize YAML to JSON |
| Type safety | Good | JSON Schema maps directly to the format |
| Ecosystem | Excellent | Native JSON parsing everywhere |

**Pros:** Simplest to produce. JSON Schema describes the exact shape. Human-readable. No binary dependency.

**Cons:** All data loaded into memory. No built-in query. Tree traversal must be implemented by every consumer. 50K-entry name index makes the file large.

---

### Option C: Auto-Generated Client Libraries

Code generation from JSON Schema produces typed client libraries per language (npm, PyPI, crates.io, Go module). Each client handles data fetching and provides a typed query API.

| Criterion | Rating | Notes |
|---|---|---|
| Portability | Good per language | N languages = N packages |
| Query capability | Can be excellent | Tree traversal, search — but implemented N times |
| Size | Good | Data embedded or fetched |
| Maintenance | **High** | N packages, N registries, N CI pipelines |
| Type safety | Excellent | Fully native types per language |
| Ecosystem | Varies | Must maintain npm, PyPI, crates.io, Go modules |

**Pros:** Best DX per language (`import { getItem } from 'gw2-data'`). Fully typed. Can embed query logic.

**Cons:** Massive maintenance burden. Query logic duplicated per language. Version skew across packages. Registry publishing requires credentials and coordination. Over-engineered for ~1,500 items.

---

### Option D: Hybrid — SQLite + Schema-Derived Types

Combine SQLite for data storage/querying with auto-generated type definitions for each language. Optionally produce a JSON bundle as a secondary artifact for consumers that prefer no-dependency in-memory loading.

| Criterion | Rating | Notes |
|---|---|---|
| Portability | Excellent | SQLite + static type files |
| Query capability | Excellent | Full SQL for SQLite consumers |
| Size | ~1MB + ~1.5MB | SQLite + optional JSON bundle |
| Maintenance | Low-Moderate | One build script + automated type generation |
| Type safety | Excellent | Generated types/interfaces per language |
| Ecosystem | Excellent | SQLite + types work everywhere |

**Pros:** Best of both worlds. Type definitions are generated artifacts, not maintained code. Tree traversal via recursive CTE. Naturally extensible — add a new language's types with one command. JSON bundle as secondary artifact is trivial.

**Cons:** Slightly more complex build pipeline. Metadata JSON blob in SQLite still needs parsing. Two artifact types per release.

---

## Summary Matrix

| Criterion | A: SQLite | B: JSON | C: Client Libs | **D: Hybrid** |
|---|---|---|---|---|
| Portability | Excellent | Excellent | Good | **Excellent** |
| Query/traversal | Excellent | Poor | Can be excellent | **Excellent** |
| Size (compressed) | ~1MB | ~1.5MB | Varies | **~1MB + ~1.5MB** |
| Maintenance | Low | Very low | High | **Low-Moderate** |
| Type safety | Moderate | Good | Excellent | **Excellent** |
| Build complexity | Low | Very low | High | **Moderate** |
| Estimated effort | ~1 day | ~0.5 day | ~1 week/lang | **~1.5 days** |

---

## Alternative Formats Considered

### Protocol Buffers

Protobuf is a serialization format, not a query engine. Consumers still load everything into memory. The polymorphic metadata (10+ types) maps awkwardly to `oneof`. Requires maintaining a `.proto` schema in sync with the JSON Schema (dual schema maintenance). At ~5MB projected data size, protobuf's binary efficiency gains over gzipped JSON are marginal.

**Verdict:** Schema duplication + build complexity without solving the core need (querying/tree traversal).

### FlatBuffers

Zero-copy deserialization — compelling for very large datasets. But at 3-8MB, full JSON deserialization takes <100ms. FlatBuffers has weaker ecosystem support than protobuf, and yet another schema format to maintain. No query capability.

**Verdict:** Solves a problem this dataset doesn't have.

---

## Recommendation: Option D (Hybrid)

### Rationale

1. **SQLite is ideal for relational data with tree traversal.** Items reference other items through requirements. Recursive CTEs handle the primary query pattern in a single SQL call. Every target language has a mature SQLite library.

2. **Schema-derived types are free.** The JSON Schema already exists and is maintained. Running `quicktype` on it is a one-line command per language. No ongoing maintenance.

3. **Minimal maintenance burden.** One Python build script reads YAML, writes SQLite. Type generation is automated. No per-language packages to publish.

4. **JSON bundle as secondary artifact.** Trivial to produce alongside SQLite. Serves consumers who prefer no-dependency in-memory loading (at the cost of manual tree traversal).

5. **Naturally extensible.** New language? Add one type-generation command. New data type? Add a table. Neither breaks existing consumers.

---

## Design Details

### Metadata: JSON Column (Not Normalized)

The 10+ metadata types have very different field sets. Normalizing into separate tables would create 10+ tables with 1-3 columns each, never queried independently. Metadata is always read alongside the acquisition — no use case for queries like "find all acquisitions with minRating > 400" without also knowing the item. SQLite's `json_extract()` can query into the blob if needed.

### Name Indexes: Separate Tables

Item names and currency names have fundamentally different cardinality:
- Item names: one-to-many (one name can map to multiple item IDs)
- Currency names: one-to-one

Separate tables allow appropriate constraints and keep queries simple.

### Full Name Index Included

The item_names table covers all ~50K items from the GW2 API, not just the ~1,500 with acquisition data. This is necessary for name-based lookups and adds ~2MB to the SQLite file (compresses to ~400KB).

### Type Generation Tooling

| Tool | Languages | Notes |
|---|---|---|
| **quicktype** | TypeScript, Go, Rust, Java, C#, Swift, ... | Best polyglot option. Single CLI per language. |
| **datamodel-code-generator** | Python (Pydantic v2) | Higher-quality Python output than quicktype. Matches existing project style. |

```bash
# TypeScript
npx quicktype --src-lang schema --src data/schema/item.schema.json --lang typescript -o dist/types/gw2-data.ts

# Rust
npx quicktype --src-lang schema --src data/schema/item.schema.json --lang rust -o dist/types/gw2_data.rs

# Go
npx quicktype --src-lang schema --src data/schema/item.schema.json --lang go -o dist/types/gw2_data.go

# Python
uv run datamodel-codegen --input data/schema/item.schema.json --output dist/types/gw2_data.py --output-model-type pydantic_v2.BaseModel
```

---

## Build Pipeline

### `scripts/build_dist.py`

Reads YAML items + name indexes, validates with Pydantic, writes:
- `dist/gw2-data.sqlite` — normalized relational database
- `dist/gw2-data.json` — single JSON bundle

Uses Python stdlib `sqlite3` (no new dependencies).

### `scripts/build_types.sh`

Runs type generation for each target language. Outputs to `dist/types/`.

### GitHub Release Workflow (`.github/workflows/release.yml`)

Triggered on tag push (`v*`):

1. Validate all YAML files
2. Run tests + lint
3. Build SQLite + JSON (`scripts/build_dist.py`)
4. Generate types (`scripts/build_types.sh`)
5. Create GitHub release with assets:
   - `gw2-data.sqlite`
   - `gw2-data.json.gz`
   - `gw2-data-types.zip` (TypeScript, Python, Rust, Go type files)
   - `item.schema.json`

### CI Workflow (`.github/workflows/ci.yml`)

On push/PR: tests, lint, validate, build_dist (smoke test).

---

## Release Artifacts

| Artifact | Description | Estimated Size |
|---|---|---|
| `gw2-data.sqlite` | SQLite database with items, acquisitions, requirements, name indexes | 3-5MB (raw), ~1MB (gzip) |
| `gw2-data.json.gz` | JSON bundle with all data | ~1.5MB |
| `gw2-data-types.zip` | Generated type definitions for TS/Python/Rust/Go | <100KB |
| `item.schema.json` | JSON Schema for consumers who want to generate their own types | <10KB |

---

## Implementation Sequence

1. Create `scripts/build_dist.py` — SQLite + JSON build script
2. Create `scripts/build_types.sh` — type generation wrapper
3. Add `datamodel-code-generator` to dev dependencies in `pyproject.toml`
4. Create `.github/workflows/release.yml`
5. Create `.github/workflows/ci.yml`
6. Test pipeline end-to-end locally
