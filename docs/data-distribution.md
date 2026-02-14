# Data Distribution

How GW2 acquisition data is packaged and distributed to external consumers.

## Overview

The raw data lives as individual YAML files (`data/items/{id}.yaml`), which is ideal for the populate/validate pipeline but impractical for external consumers. The distribution system compiles all YAML into a single compressed SQLite database published as a GitHub release artifact.

The JSON Schema (`item.schema.json`) is included alongside the database so consumers can generate typed interfaces for their language of choice.

## Release Artifacts

Each [GitHub release](https://github.com/krjackso/gw2-data-repo/releases) (triggered by pushing a `v*` tag) includes:

| Artifact | Description |
|---|---|
| `gw2-data.sqlite.gz` | Gzip-compressed SQLite database with all items, acquisitions, requirements, and name indexes |
| `item.schema.json` | JSON Schema for the YAML item format — use with [quicktype](https://quicktype.io/) or similar tools to generate types in any language |

## Database Schema

Five tables with normalized relationships:

### `items`

Item definitions sourced from the GW2 API.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | GW2 API item ID |
| `name` | TEXT NOT NULL | |
| `type` | TEXT NOT NULL | |
| `rarity` | TEXT NOT NULL | |
| `level` | INTEGER NOT NULL | |
| `icon` | TEXT | URL |
| `description` | TEXT | |
| `vendor_value` | INTEGER | |
| `flags` | TEXT | JSON array (e.g. `["AccountBound", "NoSell"]`) |
| `wiki_url` | TEXT | |
| `last_updated` | TEXT NOT NULL | ISO date |

### `acquisitions`

All acquisition methods for each item. Type-specific fields are `NULL` when not applicable.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Auto-increment |
| `item_id` | INTEGER NOT NULL | FK → `items(id)` |
| `type` | TEXT NOT NULL | e.g. `crafting`, `mystic_forge`, `vendor`, `container` |
| `vendor_name` | TEXT | For `vendor` type |
| `achievement_name` | TEXT | For `achievement` type |
| `achievement_category` | TEXT | For `achievement` type |
| `track_name` | TEXT | For `wvw_reward` / `pvp_reward` types |
| `container_item_id` | INTEGER | For `container` type (GW2 API item ID, if available) |
| `container_name` | TEXT | For `container` type |
| `node_name` | TEXT | For `resource_node` type |
| `salvage_item_id` | INTEGER | For `salvage` type (GW2 API item ID) |
| `output_quantity` | INTEGER NOT NULL | Default 1 |
| `output_quantity_min` | INTEGER | Present when output is a range |
| `output_quantity_max` | INTEGER | Present when output is a range |
| `guaranteed` | INTEGER | Boolean (0/1) for `container`, `salvage`, `resource_node` |
| `choice` | INTEGER | Boolean (0/1) for `container` |
| `metadata` | TEXT | JSON blob with type-specific fields (see CLAUDE.md for details) |

### `requirements`

Item or currency costs for each acquisition.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Auto-increment |
| `acquisition_id` | INTEGER NOT NULL | FK → `acquisitions(id)` with `ON DELETE CASCADE` |
| `item_id` | INTEGER | GW2 API item ID (mutually exclusive with `currency_id`) |
| `currency_id` | INTEGER | GW2 API currency ID (mutually exclusive with `item_id`) |
| `quantity` | INTEGER NOT NULL | |

Exactly one of `item_id` or `currency_id` must be non-NULL (enforced by CHECK constraints).

### `item_names`

Full GW2 API name-to-ID index (~57k entries). One name can map to multiple IDs.

| Column | Type |
|---|---|
| `name` | TEXT NOT NULL (composite PK) |
| `item_id` | INTEGER NOT NULL (composite PK) |

### `currency_names`

Currency name-to-ID index (~78 entries). One-to-one mapping.

| Column | Type |
|---|---|
| `name` | TEXT NOT NULL PRIMARY KEY |
| `currency_id` | INTEGER NOT NULL UNIQUE |

### Indexes

```sql
CREATE INDEX idx_acq_item ON acquisitions(item_id);
CREATE INDEX idx_acq_type ON acquisitions(type);
CREATE INDEX idx_req_acq ON requirements(acquisition_id);
CREATE INDEX idx_req_item ON requirements(item_id);
CREATE INDEX idx_req_currency ON requirements(currency_id);
CREATE INDEX idx_names ON item_names(name);
```

## Build Pipeline

### `scripts/build_dist.py`

Reads all YAML item files and name indexes, validates each item with Pydantic, and writes a normalized SQLite database to `dist/gw2-data.sqlite`. Then gzip-compresses it to `dist/gw2-data.sqlite.gz`.

Uses Python stdlib `sqlite3` — no additional dependencies.

Reference validation runs after the build and reports warnings for any item/currency IDs referenced in acquisitions or requirements that don't exist in the database. These are non-failing since the database only contains items that have been populated so far.

```bash
uv run python -m scripts.build_dist
```

### CI Workflow (`.github/workflows/ci.yml`)

Runs on every push to `main` and on pull requests:

1. Validate all YAML files
2. Run tests
3. Lint (ruff check + format)
4. Build database (smoke test)

### Release Workflow (`.github/workflows/release.yml`)

Triggered on tag push matching `v*`:

1. Validate, test, and lint (same as CI)
2. Build the SQLite database
3. Create a GitHub release with `gw2-data.sqlite.gz` and `item.schema.json`

## Design Decisions

### Why SQLite

Items reference other items through requirements, forming deep crafting trees. SQLite's recursive CTEs handle tree traversal in a single query. Every target language has a mature SQLite library (`better-sqlite3`, Python `sqlite3` stdlib, `rusqlite`, `modernc.org/sqlite`).

### Schema included, pre-built types not included

Rather than generating and shipping type definitions for every language, the release includes the JSON Schema so consumers can generate types for their own stack. This avoids maintaining type generation tooling and keeps the release simple. See the [README](../README.md) for a quicktype example.

### Metadata as JSON column

The 10+ acquisition types have different metadata fields. Normalizing these into separate tables would create many small tables that are never queried independently. Metadata is always read alongside the acquisition. SQLite's `json_extract()` can query into the blob if needed.

### Denormalized acquisition columns

Type-specific fields like `vendor_name`, `track_name`, and `container_name` are columns on the `acquisitions` table rather than in the metadata JSON blob. This makes common queries (e.g. "find all vendor acquisitions for an item") simple SQL filters without JSON parsing, while keeping the schema flat.

### Full name index included

The `item_names` table covers all ~57k items from the GW2 API, not just items with acquisition data in the database. This supports name-based lookups for any item and adds ~2MB raw (compresses well).
