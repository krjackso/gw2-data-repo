# GW2 Acquisition Data

Static dataset of all item acquisition methods for Guild Wars 2 legendary crafting. Data lives in YAML files, validated against a JSON Schema, and populated with the help of LLM extraction from wiki pages.

## Project Structure

```
gw2-data-repo/
├── data/
│   ├── items/             # YAML files: one per item, API data + acquisitions
│   ├── vendors/           # Vendor location data (generated)
│   ├── index/             # Name-to-ID indexes for items and currencies
│   └── schema/            # JSON Schema files for validation
├── src/gw2_data/
│   ├── overrides/         # Manual name/page overrides and gathering node list
│   ├── models.py          # Pydantic models matching the schema
│   ├── api.py             # GW2 API client
│   ├── wiki.py            # Wiki API client
│   ├── llm.py             # LLM extraction logic
│   └── ...                # config, cache, resolver, types, exceptions
├── scripts/               # validate, populate, populate_tree, populate_vendors, build_index
├── prompts/               # LLM prompt templates
└── tests/
```

## Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint (exclude prompts/ which contains long-line prompt strings)
uv run ruff check --exclude prompts/ .
uv run ruff format --check --exclude prompts/ .

# Validate all item YAML files (also runs automatically on commit via pre-commit hook)
uv run python -m scripts.validate

# Setup pre-commit hook (one-time setup)
pip install pre-commit
pre-commit install

# Build item or currency name-to-ID index
# IMPORTANT: NEVER run this command yourself - always ask the user to run it
uv run python -m scripts.build_index --items           # build item index (~5 min, ~57k API calls)
uv run python -m scripts.build_index --items --force   # ignore cache
uv run python -m scripts.build_index --currencies      # build currency index (< 1 sec)

# Generate item data with acquisitions
uv run python -m scripts.populate --item-id 19676 --dry-run
uv run python -m scripts.populate --item-name "Gift of Metal" --dry-run

# Use --no-strict to skip unresolvable requirements (useful for items with ambiguous names)
uv run python -m scripts.populate --item-id 19721 --no-strict --dry-run

# Recursively populate crafting tree (populates item + all dependencies)
uv run python -m scripts.populate_tree --item-id 30689 --limit 10
uv run python -m scripts.populate_tree --item-name "Eternity" --limit 5

# Process multiple root items in one run (comma-separated IDs)
uv run python -m scripts.populate_tree --item-id 30689,30690,30691 --limit 10

# Populate vendor location data from wiki
uv run python -m scripts.populate_vendors --dry-run
uv run python -m scripts.populate_vendors --vendor "Miyani" --dry-run
uv run python -m scripts.populate_vendors

# Clear cache (all or by tag: api, wiki, llm)
uv run python -m scripts.populate --clear-cache
uv run python -m scripts.populate --clear-cache api wiki
```

## Configuration

Settings can be customized via environment variables or a `.env` file:

```bash
# Copy the example file
cp .env.example .env

# Edit with your preferences
GW2_API_TIMEOUT=60.0        # Request timeout in seconds (default: 30.0)
GW2_CACHE_DIR=/tmp/cache    # Cache directory (default: .cache/gw2)
GW2_LOG_LEVEL=DEBUG         # Logging level (default: INFO)
```

All settings are optional and have sensible defaults.

## Manual Name Overrides

The file `src/gw2_data/overrides/item_name_overrides.yaml` contains manual mappings for item names that differ between the wiki and GW2 API. This is necessary when:

- **Armor weight variants**: Wiki uses semantic suffixes like "(heavy)", "(medium)", "(light)" to distinguish armor pieces, but the API returns a single name for all variants
- **Rarity variants**: When items share a name but differ by rarity (Exotic/Ascended/Legendary), the LLM automatically appends rarity qualifiers like "(Ascended)" to disambiguate. These qualified names must be mapped to the correct item IDs.
- **Alternative terminology**: Wiki uses different names than the API for the same item
- **Disambiguation**: Semantic context is needed to resolve ambiguous names

### Adding a Manual Override

1. Identify the wiki name that's failing resolution (e.g., from an error message)
2. Find the correct item ID:
   - Search `data/index/item_names.yaml` for candidate IDs
   - Check the wiki or use `uv run python -m scripts.populate --item-id <ID> --dry-run` to verify
3. Add to `src/gw2_data/overrides/item_name_overrides.yaml`:
   ```yaml
   Exact Wiki Name Here: 12345
   ```
4. Re-run populate - no index rebuild needed

**Rarity Qualifiers:**
When the LLM encounters items with multiple rarity variants on a shared wiki page (e.g., Legendary and Ascended versions of the same armor piece), it will automatically append the rarity in parentheses to requirement names. For example:
- `Triumphant Hero's Brigandine (Ascended)` → maps to ID 81434
- `Triumphant Hero's Brigandine (Legendary)` → maps to ID 84578

**Important:**
- Overrides are merged with the auto-generated index at load time
- Override entries take precedence over API names
- Use single integer IDs (not lists) for override values
- The override file is never touched by `scripts/build_index.py`

## Wiki Page Overrides

The file `src/gw2_data/overrides/wiki_page_overrides.yaml` maps item IDs to wiki page names for cases where the wiki page cannot be derived from the item name. This is necessary when:

- **Disambiguation pages**: Item name leads to a disambiguation page (e.g., "Lattice" → "Lattice (component)")
- **Non-standard suffixes**: Wiki uses a suffix other than "(item)"
- **Different page name**: Wiki article title differs from the API item name

### Adding a Wiki Page Override

1. Identify the item ID that fails wiki lookup (wrong page content or disambiguation error)
2. Find the correct wiki page URL on wiki.guildwars2.com
3. Add to `src/gw2_data/overrides/wiki_page_overrides.yaml`:
   ```yaml
   73966: 'Lattice (component)'
   ```
4. Re-run populate — the override takes effect immediately

## Strict vs Lenient Mode

By default, populate runs in **strict mode** and fails if any acquisition has unresolvable requirements. This catches typos and data quality issues.

Some items have ambiguous names that cannot be automatically resolved:
- Reward track containers with multiple variants (e.g., "Amnytas Gear Box")
- Discontinued items no longer in the API
- Other edge cases

Use `--no-strict` to skip these acquisitions instead of failing:

```bash
# Strict mode (default): fails on unresolvable
uv run python -m scripts.populate --item-name "Mystic Clover" --dry-run

# Lenient mode: skips unresolvable, continues with rest
uv run python -m scripts.populate --item-name "Mystic Clover" --no-strict --dry-run
```

In lenient mode:
- Warnings are logged for skipped acquisitions
- Only resolvable acquisitions appear in YAML
- Processing continues even with problematic items

## YAML File Format

Each file in `data/items/` contains GW2 API item data plus all acquisition methods. See existing files for full examples.

### Output Quantity Ranges

Some acquisitions produce a variable number of items (e.g., Mystic Forge promotion recipes). These use three fields together:

- `outputQuantity`: The minimum output (always present, integer ≥ 1)
- `outputQuantityMin`: Same as outputQuantity, signals this is a range (optional)
- `outputQuantityMax`: The maximum output (optional, must be ≥ outputQuantityMin)

**Fixed output:** Only `outputQuantity` is present.
**Range output:** All three fields are present.

### Container Acquisitions

Container acquisitions have a **required** `containerName` field and an optional `itemId` field. The `containerName` is the human-readable source name. When the container exists as an item in the GW2 API, `itemId` is also populated for efficient tree traversal.

### Requirements

**IMPORTANT**: All requirements MUST use IDs only (never names). The LLM extraction uses names, but the populate script automatically resolves them to IDs before writing YAML.

Two types of requirements:

```yaml
# Item requirement - requires another game item
- itemId: 19684        # GW2 API item ID
  quantity: 250

# Currency requirement - requires a game currency
- currencyId: 2        # GW2 API currency ID
  quantity: 2100
```

The resolution process:
1. LLM extracts raw entries from wiki HTML, tagged with wiki section (e.g., `recipe`, `vendor`, `gathered_from`)
2. `resolver.classify_and_resolve()` classifies entries into acquisition types and resolves names → IDs
3. For most acquisition types, if a name matches multiple IDs, an error is raised
4. **Exception for salvage acquisitions**: When a salvage source name matches multiple item IDs (e.g., armor with different weight variants), one salvage acquisition is created for each item ID. This represents items with variable costs where users can later choose the cheapest option.
5. Only IDs are written to the YAML file for efficient tree traversal

## Acquisition Types

**Important**: YAML files contain only currently obtainable acquisition paths. Discontinued or historical acquisition methods (removed items, retired reward tracks, past events) are not tracked in this dataset.

| Type | Description | Requirements | Key Fields |
|------|-------------|-------------|------------|
| `crafting` | Standard crafting at a station | Items (ingredients) | metadata: `recipeType`, `disciplines`, `minRating` |
| `mystic_forge` | Combine 4 items in the Mystic Forge | Items (ingredients) | metadata: `recipeType` |
| `vendor` | Purchase from an NPC vendor | Items + currencies (cost) | `vendorName` (top-level); metadata: `limitType`, `limitAmount`, `festival`, `notes` (notes captures special conditions, e.g. required skin, rank, or event) |
| `achievement` | Reward from completing an achievement | None | `achievementName`, `achievementCategory` (top-level); metadata: `repeatable`, `timeGated` |
| `map_reward` | World/map completion reward | None | metadata: `rewardType` (required), `regionName`, `activeTimeSeconds`, `metaName`, `notes` |
| `container` | Obtained by opening a container or chest (including named containers in "Gathered from" sections) | None | `containerName` (required), `itemId` (optional), `guaranteed`, `choice` (all top-level) |
| `salvage` | Extracted by salvaging another item | None (source in `itemId`) | `itemId`, `guaranteed` (both top-level) |
| `resource_node` | Gathered from a resource node (e.g., Rich Iron Vein, Herb Patch) | None | `nodeName`, `guaranteed` (both top-level) |
| `wvw_reward` | WvW reward track completion | None | `trackName` (top-level); metadata: `wikiUrl`, `activeTimeSeconds`, `festival` |
| `pvp_reward` | PvP reward track completion | None | `trackName` (top-level); metadata: `wikiUrl`, `activeTimeSeconds`, `festival` |
| `wizards_vault` | Wizard's Vault shop | Currency (Astral Acclaim) | metadata: `limitAmount` |
| `other` | Catch-all for edge cases (e.g., Legendary Armory) | None | metadata: `notes` (description of method) |

## Issue-Driven Development (Linear)

**CRITICAL**: When a task references a Linear issue ID (in the prompt, plan title, or context), you MUST move the issue to In Progress immediately — even before planning begins. This is always the first step — no exceptions.

**If using an issue:**
1. **Move issue to In Progress FIRST** using `/linear-cli` — do this before exploration or planning
2. **Create branch before writing any code**: `{GW2-42}-{description}` (e.g. `GW2-42-add-feature`)
3. Implement the feature
4. Self-verify acceptance criteria
5. Include Linear issue ID in commit messages: `GW2-42: Add feature`
6. After merge: Return to main, pull latest

**Commit messages**: Only describe changes present in the final diff. If something was added then reverted in the same session, do not mention it.

## Code Style

- **Always use the `/dev` skill when writing or modifying Python code** — it enforces type safety, testability, and project conventions
- Use ruff for linting and formatting
- Pydantic models use `alias` for camelCase YAML keys, snake_case Python attributes
- Tests in `tests/` directory, fixtures inline in test files
- **NEVER directly edit files in `data/items/`** — these are generated output from the populate script or hand-edited by the user. To change item data, update the schema, models, prompts, or scripts, then re-run `scripts.populate`.
- **NEVER run `scripts.build_index`** — always instruct the user to run it. The index takes ~5 minutes to build and makes ~57k API calls.
