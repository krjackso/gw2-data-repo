# GW2 Acquisition Data

Static dataset of all item acquisition methods for Guild Wars 2 legendary crafting. Data lives in YAML files, validated against a JSON Schema, and populated with the help of LLM extraction from wiki pages.

## Project Structure

```
gw2-data-repo/
├── data/
│   ├── items/             # YAML files: one per item, API data + acquisitions
│   │   └── {itemId}.yaml
│   ├── index/
│   │   └── item_names.yaml    # Name-to-ID index for lookups
│   └── schema/
│       └── item.schema.json   # JSON Schema for item files
├── src/gw2_data/
│   ├── models.py          # Pydantic models matching the schema
│   ├── config.py          # Configuration management
│   ├── cache.py           # Persistent cache client
│   ├── api.py             # GW2 API client
│   ├── wiki.py            # Wiki API client
│   ├── llm.py             # LLM extraction logic
│   ├── types.py           # TypedDict definitions
│   └── exceptions.py      # Custom exceptions
├── scripts/
│   ├── validate.py        # Validate all YAML files
│   ├── populate.py        # Generate acquisition YAML from wiki
│   ├── populate_tree.py   # Recursively populate crafting trees
│   └── build_index.py     # Build item name-to-ID index
├── prompts/               # LLM prompt templates (future)
└── tests/
    └── test_*.py          # Comprehensive test suite
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

## Data Sources

| Source | Provides | Reliability |
|--------|----------|-------------|
| **GW2 API** (`api.guildwars2.com/v2/`) | Item definitions, recipes, currencies, achievements, TP prices | High (official) |
| **GW2 Wiki** (`wiki.guildwars2.com`) | Acquisition methods, vendor info, achievement details, containers | Medium (community-maintained) |
| **LLM extraction** | Structured parsing of wiki pages into YAML | Good with validation |

## Manual Name Overrides

The file `data/index/item_name_overrides.yaml` contains manual mappings for item names that differ between the wiki and GW2 API. This is necessary when:

- **Armor weight variants**: Wiki uses semantic suffixes like "(heavy)", "(medium)", "(light)" to distinguish armor pieces, but the API returns a single name for all variants
- **Rarity variants**: When items share a name but differ by rarity (Exotic/Ascended/Legendary), the LLM automatically appends rarity qualifiers like "(Ascended)" to disambiguate. These qualified names must be mapped to the correct item IDs.
- **Alternative terminology**: Wiki uses different names than the API for the same item
- **Disambiguation**: Semantic context is needed to resolve ambiguous names

### Adding a Manual Override

1. Identify the wiki name that's failing resolution (e.g., from an error message)
2. Find the correct item ID:
   - Search `data/index/item_names.yaml` for candidate IDs
   - Check the wiki or use `uv run python -m scripts.populate --item-id <ID> --dry-run` to verify
3. Add to `data/index/item_name_overrides.yaml`:
   ```yaml
   Exact Wiki Name Here: 12345
   ```
4. Re-run populate - no index rebuild needed

**Rarity Qualifiers:**
When the LLM encounters items with multiple rarity variants on a shared wiki page (e.g., Legendary and Ascended versions of the same armor piece), it will automatically append the rarity in parentheses to requirement names. For example:
- `Triumphant Hero's Brigandine (Ascended)` → maps to ID 81434
- `Triumphant Hero's Brigandine (Legendary)` → maps to ID 84578

This ensures that Mystic Forge recipes and vendor costs correctly reference the intended variant.

**Important:**
- Overrides are merged with the auto-generated index at load time
- Override entries take precedence over API names
- Use single integer IDs (not lists) for override values
- The override file is never touched by `scripts/build_index.py`

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

Each file in `data/items/` contains GW2 API item data plus all acquisition methods:

```yaml
id: 19676
name: Gift of Metal
type: Component
rarity: Legendary
level: 0
icon: https://render.guildwars2.com/file/...
flags:
  - AccountBound
  - NoSell
wikiUrl: https://wiki.guildwars2.com/wiki/Gift_of_Metal
lastUpdated: "2025-06-15"

acquisitions:
  - type: mystic_forge
    outputQuantity: 1
    requirements:
      - itemId: 19684
        quantity: 250
      - itemId: 19683
        quantity: 250
    metadata:
      recipeType: mystic_forge

  - type: achievement
    achievementName: Lessons in Metallurgy
    achievementCategory: Collections
    outputQuantity: 1
    requirements: []
    metadata:
      repeatable: false
      timeGated: false
```

### Output Quantity Ranges

Some acquisitions produce a variable number of items (e.g., Mystic Forge promotion recipes that upgrade material tiers). These use three fields together:

- `outputQuantity`: The minimum output (always present, integer ≥ 1)
- `outputQuantityMin`: Same as outputQuantity, signals this is a range (optional)
- `outputQuantityMax`: The maximum output (optional, must be ≥ outputQuantityMin)

**Fixed output:** Only `outputQuantity` is present.
**Range output:** All three fields are present.

Example with variable output:
```yaml
- type: mystic_forge
  outputQuantity: 40
  outputQuantityMin: 40
  outputQuantityMax: 200
  requirements:
    - itemId: 20796
      quantity: 4
    - itemId: 20799
      quantity: 4
    - itemId: 24562
      quantity: 250
    - itemId: 24276
      quantity: 1
  metadata:
    recipeType: mystic_forge
```

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
1. LLM extracts acquisition data with item/currency names (human-readable)
2. `resolver.resolve_requirements()` uses the item name index to convert names → IDs
3. If a name matches multiple IDs or doesn't exist, an error is raised
4. Only IDs are written to the YAML file for efficient tree traversal

## Acquisition Types

**Important**: YAML files contain only currently obtainable acquisition paths. Discontinued or historical acquisition methods (removed items, retired reward tracks, past events) are not tracked in this dataset. The focus is on methods that are actively available in the game.

| Type | Description | Requirements | Key Metadata |
|------|-------------|-------------|--------------|
| `crafting` | Standard crafting at a station | Items (ingredients) | `recipeType`, `disciplines`, `minRating` |
| `mystic_forge` | Combine 4 items in the Mystic Forge | Items (ingredients) | `recipeType` |
| `vendor` | Purchase from an NPC vendor | Items + currencies (cost) | `vendorName` (top-level), `limitType`, `limitAmount`, `notes` |
| `achievement` | Reward from completing an achievement | None | `achievementName`, `achievementCategory` (top-level), `repeatable`, `timeGated` |
| `map_reward` | World/map completion reward | None | `rewardType`, `regionName`, `estimatedHours`, `notes` |
| `container` | Obtained by opening a container | None (source in `itemId`) | `itemId` (top-level), `guaranteed`, `choice` |
| `salvage` | Extracted by salvaging another item | None (source in `itemId`) | `itemId` (top-level), `guaranteed` |
| `wvw_reward` | WvW reward track completion | None | `trackName` (top-level), `wikiUrl` |
| `pvp_reward` | PvP reward track completion | None | `trackName` (top-level), `wikiUrl` |
| `wizards_vault` | Wizard's Vault shop | Currency (Astral Acclaim) | `limitAmount` |
| `story` | Story chapter completion reward | None | `storyChapter`, `expansion` |
| `other` | Catch-all for edge cases (e.g., Legendary Armory) | None | `notes` (description of method) |

### Vendor Notes

Vendor acquisitions may include a `notes` field in metadata to capture special conditions from the wiki, such as:
- `"Requires the skin <item name>"` - Purchase requires unlocking a specific skin first
- `"Available after completing <achievement>"` - Vendor becomes available after an achievement
- `"Only available during <event>"` - Seasonal or event-limited availability
- `"Requires <rank> in <game mode>"` - WvW/PvP rank requirements

These notes provide important context to users about prerequisites or restrictions for acquiring the item.

### Excluded Sources

**Gathering/Harvesting**: Wiki pages often include a "Gathered from" section listing gathering nodes, resource nodes, or map-specific interactable objects (e.g., "Glorious Chest (Super Adventure Box)"). These are **not tracked** because they are world objects, not items in the GW2 API, and cannot be represented as item requirements.

## GW2 Domain Knowledge

### Legendary Crafting

Legendary items are the highest-tier equipment in Guild Wars 2. Each requires a deep crafting tree (3-5 levels deep) of components obtained through various game activities.

- **~201 legendary items**: 57 weapons, 133 armor pieces (3 weights x multiple slots x multiple sets), 11 trinkets
- **~1,500 unique items** in the full dependency tree across all legendaries
- Components are heavily shared (e.g., Gift of Fortune, Mystic Clovers appear in many legendaries)
- Crafting trees mix multiple acquisition types (some components are crafted, some bought, some earned through gameplay)

### Key Crafting Systems

**Mystic Forge**: A special crafting station that combines exactly 4 items. Most legendary-specific components use this. Unlike standard crafting, Mystic Forge recipes have no discipline or level requirement.

**Standard Crafting**: Uses crafting stations with 8 disciplines (Weaponsmith, Armorsmith, Leatherworker, Tailor, Artificer, Jeweler, Huntsman, Chef) + Scribe. Each has levels 0-500. Recipes may require specific discipline and minimum level.

**Trading Post**: Player marketplace where items are bought/sold for gold. Prices fluctuate. This dataset does NOT store prices (they're dynamic), but marks items as tradable.

### Currencies

GW2 has many currencies beyond gold:

| Category | Currencies |
|----------|-----------|
| General | Gold (copper/silver/gold), Karma, Spirit Shards, Laurels |
| Raids | Magnetite Shards, Gaeting Crystals |
| Fractals | Fractal Relics, Pristine Fractal Relics |
| WvW | Badges of Honor, Skirmish Tickets |
| PvP | Shards of Glory, Ascended Shards of Glory |
| Wizard's Vault | Astral Acclaim |
| Map-specific | Volatile Magic, Unbound Magic, Trade Contracts, many more |

Currency IDs come from the GW2 API `/v2/currencies` endpoint.

### Item Binding

- **Account Bound**: Cannot be traded; must be obtained directly
- **Soulbound**: Bound to the character that acquires it
- **Unbound/Tradable**: Can be bought/sold on Trading Post

Binding affects whether an item can be bought with gold (Trading Post) or must be obtained through gameplay.

### Common Legendary Components

These appear in many legendary crafting trees:

| Item | Obtained Via |
|------|-------------|
| Gift of Exploration | World completion (map_reward) |
| Gift of Battle | WvW reward track (wvw_reward) |
| Gift of Fortune | Mystic Forge (mystic_forge) |
| Mystic Clover | Mystic Forge with RNG (mystic_forge) |
| Obsidian Shard | Multiple vendors for various currencies |
| Gift of {Material} | Mystic Forge combining 4x250 refined materials |

### GW2 API Endpoints

| Endpoint | Returns |
|----------|---------|
| `/v2/items/{id}` | Item name, type, rarity, icon, vendor value, flags |
| `/v2/recipes/{id}` | Crafting recipe ingredients, discipline, rating |
| `/v2/recipes/search?output={id}` | Find recipes that produce an item |
| `/v2/currencies` | Currency names and icons |
| `/v2/achievements/{id}` | Achievement name, description, rewards |
| `/v2/commerce/prices/{id}` | Current Trading Post buy/sell prices |
| `/v2/items?ids=...` | Bulk item lookup (up to 200 per request) |

### GW2 Wiki API

The wiki uses MediaWiki API. Key endpoints:

```
# Get raw wikitext for an item
https://wiki.guildwars2.com/api.php?action=parse&page={ItemName}&prop=wikitext&format=json

# Get rendered HTML
https://wiki.guildwars2.com/api.php?action=parse&page={ItemName}&prop=text&format=json
```

Wiki pages contain acquisition info in structured templates (`{{recipe}}`, `{{sold by}}`, `{{collection achievement}}`) and in free-text "Acquisition" sections.

## Code Style

- **Always use the `/dev` skill when writing or modifying Python code** — it enforces type safety, testability, and project conventions
- No explanatory comments or docstrings unless explicitly instructed
- Use ruff for linting and formatting
- Pydantic models use `alias` for camelCase YAML keys, snake_case Python attributes
- Tests in `tests/` directory, fixtures inline in test files
- **NEVER directly edit files in `data/items/`** — these are generated output from the populate script or hand-edited by the user. To change item data, update the schema, models, prompts, or scripts, then re-run `scripts.populate`.
- **NEVER run `scripts.build_index`** — always instruct the user to run it. The index takes ~5 minutes to build and makes ~57k API calls.
