# GW2 Acquisition Data

## Building the Item Name Index

The item name index maps item names to their GW2 API item IDs, enabling lookups by name instead of numeric ID.

### Prerequisites

```bash
uv sync
```

### Build the index

```bash
uv run python -m scripts.build_index
```

This fetches all ~57k items from the GW2 API in batches of 200 and writes a YAML index to `data/index/item_names.yaml`. Results are cached, so subsequent runs are fast.

To bypass the cache and re-fetch everything:

```bash
uv run python -m scripts.build_index --force
```

### Using the index

Once built, the index enables name-based lookups in the populate script:

```bash
uv run python -m scripts.populate --item-name "Gift of Metal" --dry-run
```

If multiple items share the same name, the script will list the matching IDs so you can disambiguate with `--item-id`.
