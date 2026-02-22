import gzip
import json
import logging
import sqlite3
from pathlib import Path

import yaml

from src.gw2_data.models import ItemFile

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DIST_DIR = REPO_ROOT / "dist"
DATA_DIR = REPO_ROOT / "data"
INDEX_DIR = DATA_DIR / "index"
ITEMS_DIR = DATA_DIR / "items"

SCHEMA = """
CREATE TABLE items (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL,
    rarity       TEXT NOT NULL,
    level        INTEGER NOT NULL,
    icon         TEXT,
    description  TEXT,
    vendor_value INTEGER,
    flags        TEXT,
    wiki_url     TEXT,
    last_updated TEXT NOT NULL
);

CREATE TABLE acquisitions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id              INTEGER NOT NULL REFERENCES items(id),
    type                 TEXT NOT NULL,
    vendor_name          TEXT,
    achievement_name     TEXT,
    achievement_category TEXT,
    track_name           TEXT,
    container_item_id    INTEGER,
    container_name       TEXT,
    node_name            TEXT,
    salvage_item_id      INTEGER,
    output_quantity      INTEGER NOT NULL DEFAULT 1,
    output_quantity_min  INTEGER,
    output_quantity_max  INTEGER,
    guaranteed           INTEGER,
    choice               INTEGER,
    metadata             TEXT
);

CREATE TABLE requirements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    acquisition_id  INTEGER NOT NULL REFERENCES acquisitions(id) ON DELETE CASCADE,
    item_id         INTEGER,
    currency_id     INTEGER,
    quantity        INTEGER NOT NULL,
    CHECK (item_id IS NOT NULL OR currency_id IS NOT NULL),
    CHECK (item_id IS NULL OR currency_id IS NULL)
);

CREATE TABLE item_names (
    name    TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    PRIMARY KEY (name, item_id)
);

CREATE TABLE currency_names (
    name        TEXT NOT NULL PRIMARY KEY,
    currency_id INTEGER NOT NULL UNIQUE
);

CREATE INDEX idx_acq_item ON acquisitions(item_id);
CREATE INDEX idx_acq_type ON acquisitions(type);
CREATE INDEX idx_req_acq ON requirements(acquisition_id);
CREATE INDEX idx_req_item ON requirements(item_id);
CREATE INDEX idx_req_currency ON requirements(currency_id);
CREATE INDEX idx_names ON item_names(name);
"""


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def build_database(db_path: Path) -> None:
    logger.info("Creating SQLite database at %s", db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys = OFF")

        logger.info("Creating schema...")
        cursor.executescript(SCHEMA)

        logger.info("Loading item files...")
        item_files = sorted(ITEMS_DIR.glob("*.yaml"))
        logger.info("Found %d item files", len(item_files))

        items_inserted = 0
        acquisitions_inserted = 0
        requirements_inserted = 0

        for item_file in item_files:
            with open(item_file) as f:
                data = yaml.safe_load(f)

            item = ItemFile.model_validate(data)

            flags_json = json.dumps(item.flags) if item.flags else None

            cursor.execute(
                """
                INSERT INTO items (
                    id, name, type, rarity, level, icon, description,
                    vendor_value, flags, wiki_url, last_updated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.name,
                    item.type,
                    item.rarity,
                    item.level,
                    item.icon,
                    item.description,
                    item.vendor_value,
                    flags_json,
                    item.wiki_url,
                    item.last_updated,
                ),
            )
            items_inserted += 1

            if item.acquisitions:
                for acq in item.acquisitions:
                    salvage_item_id = acq.item_id if acq.type == "salvage" else None
                    container_item_id = acq.item_id if acq.type == "container" else None

                    metadata_json = None
                    if acq.metadata is not None:
                        if isinstance(acq.metadata, dict):
                            metadata_json = json.dumps(acq.metadata)
                        else:
                            metadata_json = acq.metadata.model_dump_json(
                                by_alias=True, exclude_none=True
                            )

                    cursor.execute(
                        """
                        INSERT INTO acquisitions (
                            item_id, type, vendor_name, achievement_name,
                            achievement_category, track_name, container_item_id,
                            container_name, node_name, salvage_item_id,
                            output_quantity, output_quantity_min,
                            output_quantity_max, guaranteed, choice, metadata
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.id,
                            acq.type,
                            acq.vendor_name,
                            acq.achievement_name,
                            acq.achievement_category,
                            acq.track_name,
                            container_item_id,
                            acq.container_name,
                            acq.node_name,
                            salvage_item_id,
                            acq.output_quantity,
                            acq.output_quantity_min,
                            acq.output_quantity_max,
                            _bool_to_int(acq.guaranteed),
                            _bool_to_int(acq.choice),
                            metadata_json,
                        ),
                    )
                    acquisition_id = cursor.lastrowid
                    acquisitions_inserted += 1

                    if acq.requirements:
                        for req in acq.requirements:
                            if hasattr(req, "item_id"):
                                cursor.execute(
                                    """
                                    INSERT INTO requirements (acquisition_id, item_id, quantity)
                                    VALUES (?, ?, ?)
                                    """,
                                    (acquisition_id, req.item_id, req.quantity),
                                )
                            else:
                                cursor.execute(
                                    """
                                    INSERT INTO requirements (acquisition_id, currency_id, quantity)
                                    VALUES (?, ?, ?)
                                    """,
                                    (acquisition_id, req.currency_id, req.quantity),
                                )
                            requirements_inserted += 1

        logger.info("Inserted %d items", items_inserted)
        logger.info("Inserted %d acquisitions", acquisitions_inserted)
        logger.info("Inserted %d requirements", requirements_inserted)

        logger.info("Loading item name index...")
        with open(INDEX_DIR / "item_names.yaml") as f:
            item_names = yaml.safe_load(f)

        item_names_inserted = 0
        for name, item_ids in item_names.items():
            if isinstance(item_ids, int):
                item_ids = [item_ids]
            for item_id in item_ids:
                cursor.execute(
                    "INSERT INTO item_names (name, item_id) VALUES (?, ?)",
                    (name, item_id),
                )
                item_names_inserted += 1

        logger.info("Inserted %d item name mappings", item_names_inserted)

        logger.info("Loading currency name index...")
        with open(INDEX_DIR / "currency_names.yaml") as f:
            currency_names = yaml.safe_load(f)

        currency_names_inserted = 0
        for name, currency_id in currency_names.items():
            cursor.execute(
                "INSERT INTO currency_names (name, currency_id) VALUES (?, ?)",
                (name, currency_id),
            )
            currency_names_inserted += 1

        logger.info("Inserted %d currency name mappings", currency_names_inserted)

        logger.info("Enabling foreign keys and verifying integrity...")
        cursor.execute("PRAGMA foreign_keys = ON")
        violations = cursor.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Foreign key violations found: {violations}")

        logger.info("Committing transaction...")
        conn.commit()

        logger.info("Running VACUUM to optimize database size...")
        conn.execute("VACUUM")

        logger.info("Database build complete")

    except Exception:
        logger.error("Build failed, rolling back transaction")
        conn.rollback()
        raise
    finally:
        conn.close()


def validate_references(db_path: Path) -> None:
    logger.info("Validating item and currency references...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    warnings = []

    missing_container_items = cursor.execute(
        """
        SELECT DISTINCT a.container_item_id
        FROM acquisitions a
        WHERE a.container_item_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM items WHERE id = a.container_item_id)
        ORDER BY a.container_item_id
        """
    ).fetchall()

    if missing_container_items:
        ids = [str(row[0]) for row in missing_container_items]
        msg = f"Found {len(missing_container_items)} container item(s) not in database: "
        warnings.append(msg + ", ".join(ids))

    missing_salvage_items = cursor.execute(
        """
        SELECT DISTINCT a.salvage_item_id
        FROM acquisitions a
        WHERE a.salvage_item_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM items WHERE id = a.salvage_item_id)
        ORDER BY a.salvage_item_id
        """
    ).fetchall()

    if missing_salvage_items:
        ids = [str(row[0]) for row in missing_salvage_items]
        msg = f"Found {len(missing_salvage_items)} salvage source item(s) not in database: "
        warnings.append(msg + ", ".join(ids))

    missing_requirement_items = cursor.execute(
        """
        SELECT DISTINCT r.item_id
        FROM requirements r
        WHERE r.item_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM items WHERE id = r.item_id)
        ORDER BY r.item_id
        """
    ).fetchall()

    if missing_requirement_items:
        ids = [str(row[0]) for row in missing_requirement_items]
        msg = f"Found {len(missing_requirement_items)} requirement item(s) not in database: "
        warnings.append(msg + ", ".join(ids))

    missing_requirement_currencies = cursor.execute(
        """
        SELECT DISTINCT r.currency_id
        FROM requirements r
        WHERE r.currency_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM currency_names WHERE currency_id = r.currency_id)
        ORDER BY r.currency_id
        """
    ).fetchall()

    if missing_requirement_currencies:
        ids = [str(row[0]) for row in missing_requirement_currencies]
        msg = f"Found {len(missing_requirement_currencies)} requirement currency(ies) not in database: "
        warnings.append(msg + ", ".join(ids))

    conn.close()

    if warnings:
        logger.warning("\n" + "\n".join(["⚠️  Reference Validation Warnings:"] + warnings))
        logger.warning("\nThese items/currencies are referenced but not in the database.")
        logger.warning(
            "This is expected - the database only contains items that have been populated."
        )
    else:
        logger.info("All item and currency references are valid ✓")


def compress_database(db_path: Path, gz_path: Path) -> None:
    logger.info("Compressing database to %s", gz_path)

    with open(db_path, "rb") as f_in:
        with gzip.open(gz_path, "wb", compresslevel=9) as f_out:
            f_out.write(f_in.read())

    db_size = db_path.stat().st_size
    gz_size = gz_path.stat().st_size
    compression_ratio = (1 - gz_size / db_size) * 100

    logger.info(
        "Compression complete: %d bytes -> %d bytes (%.1f%% reduction)",
        db_size,
        gz_size,
        compression_ratio,
    )


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    db_path = DIST_DIR / "gw2-data.sqlite"
    gz_path = DIST_DIR / "gw2-data.sqlite.gz"

    if db_path.exists():
        logger.info("Removing existing database...")
        db_path.unlink()

    if gz_path.exists():
        logger.info("Removing existing compressed database...")
        gz_path.unlink()

    build_database(db_path)
    validate_references(db_path)
    compress_database(db_path, gz_path)

    logger.info("Build complete!")
    logger.info("  Database: %s", db_path)
    logger.info("  Compressed: %s", gz_path)


if __name__ == "__main__":
    main()
