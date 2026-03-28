import aiosqlite
import json
from typing import Optional

DB_PATH = "reservations.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                table_id    INTEGER NOT NULL,
                slot_id     INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                username    TEXT    NOT NULL,
                confirmed   INTEGER DEFAULT NULL,
                UNIQUE(date, table_id, slot_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_posts (
                date             TEXT PRIMARY KEY,
                channel_id       INTEGER NOT NULL,
                thread_id        INTEGER NOT NULL,
                table_message_ids TEXT NOT NULL
            )
        """)
        await db.commit()


# ── Reservations ────────────────────────────────────────────────────────────

async def get_reservation(date: str, table_id: int, slot_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reservations WHERE date=? AND table_id=? AND slot_id=?",
            (date, table_id, slot_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_day_reservations(date: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reservations WHERE date=?", (date,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_user_reservations_for_date(date: str, user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reservations WHERE date=? AND user_id=?",
            (date, user_id),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_unconfirmed_reservations_for_date(date: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM reservations WHERE date=? AND confirmed IS NULL", (date,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def create_reservation(
    date: str, table_id: int, slot_id: int, user_id: int, username: str
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO reservations (date, table_id, slot_id, user_id, username) "
                "VALUES (?,?,?,?,?)",
                (date, table_id, slot_id, user_id, username),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def delete_reservation(
    date: str, table_id: int, slot_id: int, user_id: int
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM reservations WHERE date=? AND table_id=? AND slot_id=? AND user_id=?",
            (date, table_id, slot_id, user_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def admin_delete_reservation(date: str, table_id: int, slot_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM reservations WHERE date=? AND table_id=? AND slot_id=?",
            (date, table_id, slot_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def update_confirmation(
    date: str, table_id: int, slot_id: int, confirmed: bool
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reservations SET confirmed=? WHERE date=? AND table_id=? AND slot_id=?",
            (1 if confirmed else 0, date, table_id, slot_id),
        )
        await db.commit()


# ── Daily posts ──────────────────────────────────────────────────────────────

async def save_daily_post(
    date: str, channel_id: int, thread_id: int, table_message_ids: dict
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO daily_posts "
            "(date, channel_id, thread_id, table_message_ids) VALUES (?,?,?,?)",
            (date, channel_id, thread_id, json.dumps(table_message_ids)),
        )
        await db.commit()


async def get_daily_post(date: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM daily_posts WHERE date=?", (date,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["table_message_ids"] = json.loads(d["table_message_ids"])
            return d
