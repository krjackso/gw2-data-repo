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

# Lint
uv run ruff check .
uv run ruff format --check .

# Validate all item YAML files
uv run python -m scripts.validate

# Build item name-to-ID index (fetches all ~57k items from GW2 API)
uv run python -m scripts.build_index
uv run python -m scripts.build_index --force          # ignore cache

# Generate item data with acquisitions
uv run python -m scripts.populate --item-id 19676 --dry-run
uv run python -m scripts.populate --item-name "Gift of Metal" --dry-run

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
    outputQuantity: 1
    requirements: []
    metadata:
      achievementName: Lessons in Metallurgy
      achievementCategory: Collections
      repeatable: false
      timeGated: false
```

### Requirements

Two types of requirements (all resolved to IDs upfront):

```yaml
# Item requirement - requires another game item
- itemId: 19684        # GW2 API item ID
  quantity: 250

# Currency requirement - requires a game currency
- currencyId: 2        # GW2 API currency ID
  quantity: 2100
```

## Acquisition Types

| Type | Description | Requirements | Key Metadata |
|------|-------------|-------------|--------------|
| `crafting` | Standard crafting at a station | Items (ingredients) | `recipeType`, `disciplines`, `minRating` |
| `mystic_forge` | Combine 4 items in the Mystic Forge | Items (ingredients) | `recipeType` |
| `vendor` | Purchase from an NPC vendor | Items + currencies (cost) | `vendorName` (top-level), `limitType`, `limitAmount` |

| `achievement` | Reward from completing an achievement | None | `achievementName`, `achievementCategory`, `repeatable`, `timeGated` |
| `map_reward` | World/map completion reward | None | `rewardType`, `regionName`, `estimatedHours`, `notes` |
| `container` | Obtained by opening a container | Item (the container) | `guaranteed` |
| `salvage` | Extracted by salvaging another item | Item (source) | `guaranteed` |
| `wvw_reward` | WvW reward track completion | None | `trackName`, `trackType`, `wikiUrl` |
| `pvp_reward` | PvP reward track completion | None | `trackName`, `trackType`, `wikiUrl` |
| `wizards_vault` | Wizard's Vault seasonal shop | Currency (Astral Acclaim) | `seasonal` |
| `story` | Story chapter completion reward | None | `storyChapter`, `expansion` |

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

- No explanatory comments or docstrings unless explicitly instructed
- Use ruff for linting and formatting
- Pydantic models use `alias` for camelCase YAML keys, snake_case Python attributes
- Tests in `tests/` directory, fixtures inline in test files
- **NEVER directly edit files in `data/items/`** — these are generated output from the populate script or hand-edited by the user. To change item data, update the schema, models, prompts, or scripts, then re-run `scripts.populate`.
