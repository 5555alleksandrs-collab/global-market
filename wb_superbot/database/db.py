"""
База данных SQLite. Используется aiosqlite для асинхронной работы.
"""

from __future__ import annotations

import aiosqlite
import logging
from config import config

logger = logging.getLogger(__name__)
DB_PATH = config.DB_PATH


async def init_db():
    """Создаёт таблицы если их нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;

            -- Пользователи бота
            CREATE TABLE IF NOT EXISTS users (
                tg_id        INTEGER PRIMARY KEY,
                username     TEXT,
                full_name    TEXT,
                wb_token     TEXT,          -- токен продавца WB (если несколько кабинетов)
                subscribed   INTEGER DEFAULT 0,   -- 1 = подписка активна
                sub_until    TEXT,                -- дата окончания подписки ISO
                autobrons    INTEGER DEFAULT 0,   -- баланс авто-броней
                access_approved INTEGER DEFAULT 0,   -- доступ в бота одобрен админом
                access_requested INTEGER DEFAULT 0,  -- пользователь уже отправлял заявку
                created_at   TEXT DEFAULT (datetime('now'))
            );

            -- Заявки на авто-бронирование
            CREATE TABLE IF NOT EXISTS autobron_tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id        INTEGER NOT NULL,
                draft_id     TEXT NOT NULL,       -- ID черновика в WB
                warehouse_id TEXT NOT NULL,
                supply_type  TEXT NOT NULL,       -- box | pallet | supersafe
                date_from    TEXT NOT NULL,       -- ISO дата начала периода
                date_to      TEXT NOT NULL,       -- ISO дата конца периода
                max_coef     INTEGER NOT NULL,    -- максимальный коэффициент (0..20)
                protection   INTEGER DEFAULT 1,   -- 1=защита включена (+72ч)
                status       TEXT DEFAULT 'active',  -- active | done | archived
                booked_date  TEXT,                -- дата успешного бронирования
                created_at   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (tg_id) REFERENCES users(tg_id)
            );

            -- Заявки на поиск таймслотов
            CREATE TABLE IF NOT EXISTS timeslot_tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id        INTEGER NOT NULL,
                warehouse_id TEXT NOT NULL,
                supply_type  TEXT NOT NULL,
                date_from    TEXT NOT NULL,
                date_to      TEXT NOT NULL,
                max_coef     INTEGER NOT NULL,
                status       TEXT DEFAULT 'active',   -- active | done
                created_at   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (tg_id) REFERENCES users(tg_id)
            );

            -- Заявки на перераспределение
            CREATE TABLE IF NOT EXISTS redistribution_tasks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id           INTEGER NOT NULL,
                article         TEXT NOT NULL,
                from_warehouse  TEXT NOT NULL,
                to_warehouse    TEXT NOT NULL,
                quantity        INTEGER NOT NULL,
                status          TEXT DEFAULT 'active',
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (tg_id) REFERENCES users(tg_id)
            );

            -- История оплат
            CREATE TABLE IF NOT EXISTS payments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id        INTEGER NOT NULL,
                amount       INTEGER NOT NULL,
                service      TEXT NOT NULL,    -- subscription | autobron_N | redistribution_N
                status       TEXT DEFAULT 'pending',  -- pending | paid | failed
                payment_id   TEXT,
                created_at   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (tg_id) REFERENCES users(tg_id)
            );
        """)
        # Миграции для существующей БД (если таблица users уже была создана раньше)
        async with db.execute("PRAGMA table_info(users)") as cur:
            columns = {row[1] for row in await cur.fetchall()}
        if "access_approved" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN access_approved INTEGER DEFAULT 0"
            )
        if "access_requested" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN access_requested INTEGER DEFAULT 0"
            )
        await db.commit()
    logger.info("База данных инициализирована: %s", DB_PATH)


async def get_user(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def is_user_approved(tg_id: int) -> bool:
    user = await get_user(tg_id)
    return bool(user and user.get("access_approved", 0))


async def mark_access_requested(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET access_requested=1 WHERE tg_id=?",
            (tg_id,),
        )
        await db.commit()


async def approve_user_access(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET access_approved=1, access_requested=0 WHERE tg_id=?",
            (tg_id,),
        )
        await db.commit()


async def get_pending_access_requests() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT tg_id, username, full_name, created_at "
            "FROM users WHERE access_approved=0 AND access_requested=1 "
            "ORDER BY created_at DESC LIMIT 100"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def upsert_user(tg_id: int, username: str = "", full_name: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (tg_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
            """,
            (tg_id, username, full_name),
        )
        await db.commit()


async def set_wb_token(tg_id: int, token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET wb_token = ? WHERE tg_id = ?", (token, tg_id)
        )
        await db.commit()


async def deduct_autobrons(tg_id: int, count: int) -> bool:
    """Списывает авто-брони. Возвращает True если успешно."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT autobrons FROM users WHERE tg_id = ?", (tg_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row or row[0] < count:
            return False
        await db.execute(
            "UPDATE users SET autobrons = autobrons - ? WHERE tg_id = ?",
            (count, tg_id),
        )
        await db.commit()
        return True


async def add_autobrons(tg_id: int, count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET autobrons = autobrons + ? WHERE tg_id = ?",
            (count, tg_id),
        )
        await db.commit()


async def create_autobron_task(
    tg_id: int,
    draft_id: str,
    warehouse_id: str,
    supply_type: str,
    date_from: str,
    date_to: str,
    max_coef: int,
    protection: int = 1,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO autobron_tasks
                (tg_id, draft_id, warehouse_id, supply_type, date_from, date_to, max_coef, protection)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tg_id, draft_id, warehouse_id, supply_type, date_from, date_to, max_coef, protection),
        )
        await db.commit()
        return cur.lastrowid


async def get_active_autobron_tasks() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT t.*, u.wb_token FROM autobron_tasks t "
            "JOIN users u ON t.tg_id = u.tg_id "
            "WHERE t.status = 'active'"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def complete_autobron_task(task_id: int, booked_date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE autobron_tasks SET status='done', booked_date=? WHERE id=?",
            (booked_date, task_id),
        )
        await db.commit()


async def archive_autobron_task(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE autobron_tasks SET status='archived' WHERE id=?", (task_id,)
        )
        await db.commit()


async def delete_autobron_task(task_id: int, tg_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        # Возвращаем авто-бронь если задача была активной
        async with db.execute(
            "SELECT status FROM autobron_tasks WHERE id=? AND tg_id=?",
            (task_id, tg_id),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        if row[0] == "active":
            await db.execute(
                "UPDATE users SET autobrons = autobrons + 1 WHERE tg_id = ?", (tg_id,)
            )
        await db.execute(
            "DELETE FROM autobron_tasks WHERE id=? AND tg_id=?", (task_id, tg_id)
        )
        await db.commit()
        return True


async def get_user_autobron_tasks(tg_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM autobron_tasks WHERE tg_id=? ORDER BY created_at DESC LIMIT 50",
            (tg_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def create_timeslot_task(
    tg_id: int,
    warehouse_id: str,
    supply_type: str,
    date_from: str,
    date_to: str,
    max_coef: int,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO timeslot_tasks
                (tg_id, warehouse_id, supply_type, date_from, date_to, max_coef)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tg_id, warehouse_id, supply_type, date_from, date_to, max_coef),
        )
        await db.commit()
        return cur.lastrowid


async def get_active_timeslot_tasks() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT t.*, u.wb_token FROM timeslot_tasks t "
            "JOIN users u ON t.tg_id = u.tg_id "
            "WHERE t.status = 'active'"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def create_redistribution_task(
    tg_id: int,
    article: str,
    from_warehouse: str,
    to_warehouse: str,
    quantity: int,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO redistribution_tasks
                (tg_id, article, from_warehouse, to_warehouse, quantity)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tg_id, article, from_warehouse, to_warehouse, quantity),
        )
        await db.commit()
        return cur.lastrowid


async def get_active_redistribution_tasks() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT t.*, u.wb_token FROM redistribution_tasks t "
            "JOIN users u ON t.tg_id = u.tg_id "
            "WHERE t.status = 'active'"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def record_payment(tg_id: int, amount: int, service: str, payment_id: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO payments (tg_id, amount, service, payment_id) VALUES (?, ?, ?, ?)",
            (tg_id, amount, service, payment_id),
        )
        await db.commit()
        return cur.lastrowid


async def confirm_payment(payment_db_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status='paid' WHERE id=?", (payment_db_id,)
        )
        await db.commit()


async def get_payment_history(tg_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE tg_id=? ORDER BY created_at DESC LIMIT 30",
            (tg_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
