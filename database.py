import aiosqlite

DB_PATH = "stake_pay.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id TEXT,
                creator_id INTEGER,
                target_id INTEGER,
                asset TEXT,
                amount REAL,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                asset TEXT,
                amount REAL,
                address TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            return await cur.fetchone()


async def create_user(user_id: int, username: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()


async def update_balance(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def save_check(check_id, creator_id, target_id, asset, amount, description):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO checks (check_id, creator_id, target_id, asset, amount, description) VALUES (?, ?, ?, ?, ?, ?)",
            (check_id, creator_id, target_id, asset, amount, description)
        )
        await db.commit()


async def get_check(check_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM checks WHERE check_id = ?", (check_id,)) as cur:
            return await cur.fetchone()


async def activate_check(check_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE checks SET status = 'activated' WHERE check_id = ?", (check_id,))
        await db.commit()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*), SUM(amount) FROM checks WHERE status = 'activated'") as cur:
            return await cur.fetchone()


# ---------- WITHDRAWALS ----------
async def create_withdrawal(user_id, asset, amount, address):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO withdrawals (user_id, asset, amount, address) VALUES (?, ?, ?, ?)",
            (user_id, asset, amount, address)
        )
        await db.commit()


async def get_pending_withdrawals():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM withdrawals WHERE status = 'pending'") as cur:
            return await cur.fetchall()


async def get_withdrawal(wid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM withdrawals WHERE id = ?", (wid,)) as cur:
            return await cur.fetchone()


async def update_withdrawal_status(wid: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE withdrawals SET status = ? WHERE id = ?", (status, wid))
        await db.commit()
