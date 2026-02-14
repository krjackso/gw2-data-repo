# GW2 Acquisition Data

Static dataset of all item acquisition methods for Guild Wars 2 legendary crafting. Data lives in YAML files, validated against a JSON Schema, and distributed as a compressed SQLite database.

## Distribution & Usage

### Download Latest Release

Download the latest release from the [GitHub releases page](https://github.com/krjackso/gw2-data-repo/releases).

Each release includes:
- `gw2-data.sqlite.gz` - Compressed SQLite database (~1MB)
- `item.schema.json` - JSON Schema for type generation

Extract the database:
```bash
gunzip gw2-data.sqlite.gz
```

### Database Schema

The SQLite database contains five tables:

| Table | Description |
|-------|-------------|
| `items` | Item definitions from GW2 API (id, name, type, rarity, level, icon, flags, etc.) |
| `acquisitions` | All acquisition methods for each item (type, vendor, achievement, container, etc.) |
| `requirements` | Item/currency requirements for each acquisition |
| `item_names` | Name-to-ID index for lookups (one-to-many) |
| `currency_names` | Currency name-to-ID index (one-to-one) |

For full schema details, see [`docs/data-distribution.md`](docs/data-distribution.md).

### Example SQL Queries

**Lookup item by ID:**
```sql
SELECT * FROM items WHERE id = 19676;
```

**Lookup item ID by name:**
```sql
SELECT i.id, i.name, i.rarity
FROM items i
JOIN item_names n ON n.item_id = i.id
WHERE n.name = 'Gift of Metal';
```

**Lookup currency ID by name:**
```sql
SELECT currency_id, name
FROM currency_names
WHERE name = 'Coin';
```

**Recursive tree traversal (find all dependencies):**
```sql
WITH RECURSIVE tree(item_id, depth, path) AS (
    SELECT 19676, 0, '19676'
    UNION ALL
    SELECT r.item_id, t.depth + 1, t.path || ',' || r.item_id
    FROM tree t
    JOIN acquisitions a ON a.item_id = t.item_id
    JOIN requirements r ON r.acquisition_id = a.id
    WHERE r.item_id IS NOT NULL
      AND t.depth < 10
      AND instr(t.path, ',' || r.item_id || ',') = 0
)
SELECT DISTINCT i.* FROM tree t JOIN items i ON i.id = t.item_id;
```

### Type Generation

Generate TypeScript types from the JSON Schema using [quicktype](https://quicktype.io/):

```bash
pnpm add -D quicktype
pnpm exec quicktype --src-lang schema --src item.schema.json --lang typescript --out gw2-types.ts
```

Quicktype also supports Python, Rust, Go, Java, and many other languages. See the [quicktype documentation](https://quicktype.io/) for details.

### Library Integration Examples

**TypeScript with better-sqlite3:**
```typescript
import Database from 'better-sqlite3';

const db = new Database('gw2-data.sqlite');

// Lookup item by name
const item = db.prepare(`
  SELECT i.* FROM items i
  JOIN item_names n ON n.item_id = i.id
  WHERE n.name = ?
`).get('Gift of Metal');

// Get crafting tree
const tree = db.prepare(`
  WITH RECURSIVE tree(item_id, depth) AS (
    SELECT ?, 0
    UNION ALL
    SELECT r.item_id, t.depth + 1
    FROM tree t
    JOIN acquisitions a ON a.item_id = t.item_id
    JOIN requirements r ON r.acquisition_id = a.id
    WHERE r.item_id IS NOT NULL AND t.depth < 10
  )
  SELECT DISTINCT i.* FROM tree t JOIN items i ON i.id = t.item_id
`).all(30704);
```

## Development

See [`CLAUDE.md`](CLAUDE.md) for full development documentation including:
- Project structure
- Commands for populating data
- Manual name overrides
- Acquisition types reference
- GW2 domain knowledge

### Building the Item Name Index

The item name index maps item names to their GW2 API item IDs, enabling lookups by name instead of numeric ID.

**Prerequisites:**
```bash
uv sync
```

**Build the index:**
```bash
uv run python -m scripts.build_index --items
```

This fetches all ~57k items from the GW2 API in batches of 200 and writes a YAML index to `data/index/item_names.yaml`. Results are cached, so subsequent runs are fast.

To bypass the cache and re-fetch everything:
```bash
uv run python -m scripts.build_index --items --force
```

**Using the index:**

Once built, the index enables name-based lookups in the populate script:
```bash
uv run python -m scripts.populate --item-name "Gift of Metal" --dry-run
```

If multiple items share the same name, the script will list the matching IDs so you can disambiguate with `--item-id`.
