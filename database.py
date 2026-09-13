import sqlite3
import asyncio

DB_PATH = "stake_pay.db"


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS own_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            creator_id INTEGER,
            target_id INTEGER,
            target_username TEXT,
            asset TEXT,
            amount REAL,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            asset TEXT,
            amount REAL,
            tx_id TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def _create_user(user_id, username=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()


def _update_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def _set_balance(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def _ban_user(user_id, ban: bool):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if ban else 0, user_id))
    conn.commit()
    conn.close()


def _all_users():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT user_id, username, balance, is_banned, created_at FROM users ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def _log_admin(admin_id, action, target_id, details):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
        (admin_id, action, target_id, details)
    )
    conn.commit()
    conn.close()


def _create_deposit(user_id, asset, amount, tx_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO deposits (user_id, asset, amount, tx_id) VALUES (?, ?, ?, ?)",
            (user_id, asset, amount, tx_id)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# ===== СВОИ ЧЕКИ (без CryptoBot) =====
def _create_own_check(code, creator_id, target_id, target_username, asset, amount, description):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO own_checks (code, creator_id, target_id, target_username, asset, amount, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (code, creator_id, target_id, target_username, asset, amount, description)
    )
    conn.commit()
    conn.close()


def _get_own_check(code):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM own_checks WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row


def _activate_own_check(code):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE own_checks SET status = 'activated' WHERE code = ?", (code,))
    conn.commit()
    conn.close()


# ===== ASYNC ОБЁРТКИ =====
async def init_db():
    await asyncio.to_thread(_init_db)


async def get_user(user_id):
    return await asyncio.to_thread(_get_user, user_id)


async def create_user(user_id, username=""):
    await asyncio.to_thread(_create_user, user_id, username)


async def update_balance(user_id, amount):
    await asyncio.to_thread(_update_balance, user_id, amount)


async def set_balance(user_id, amount):
    await asyncio.to_thread(_set_balance, user_id, amount)


async def ban_user(user_id, ban=True):
    await asyncio.to_thread(_ban_user, user_id, ban)


async def all_users():
    return await asyncio.to_thread(_all_users)


async def log_admin(admin_id, action, target_id, details):
    await asyncio.to_thread(_log_admin, admin_id, action, target_id, details)


async def create_deposit(user_id, asset, amount, tx_id):
    return await asyncio.to_thread(_create_deposit, user_id, asset, amount, tx_id)


async def create_own_check(code, creator_id, target_id, target_username, asset, amount, description):
    await asyncio.to_thread(_create_own_check, code, creator_id, target_id, target_username, asset, amount, description)


async def get_own_check(code):
    return await asyncio.to_thread(_get_own_check, code)


async def activate_own_check(code):
    await asyncio.to_thread(_activate_own_check, code)


# ===== ЧЕКИ CryptoBot (старые — оставлены для совместимости) =====
async def save_check(check_id, creator_id, target_id, asset, amount, description):
    def _save():
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO own_checks (code, creator_id, target_id, asset, amount, description) VALUES (?, ?, ?, ?, ?, ?)",
            (check_id, creator_id, target_id, asset, amount, description)
        )
        conn.commit()
        conn.close()
    await asyncio.to_thread(_save)


async def get_check(check_id):
    return await get_own_check(check_id)


async def activate_check(check_id):
    await activate_own_check(check_id)


async def get_stats():
    def _stats():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT COUNT(*), SUM(amount) FROM own_checks WHERE status = 'activated'")
        row = cur.fetchone()
        conn.close()
        return row
    return await asyncio.to_thread(_stats)


async def create_withdrawal(user_id, asset, amount, address):
    def _create():
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO withdrawals (user_id, asset, amount, address) VALUES (?, ?, ?, ?)",
            (user_id, asset, amount, address)
        )
        conn.commit()
        conn.close()
    await asyncio.to_thread(_create)


async def get_pending_withdrawals():
    def _get():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT * FROM withdrawals WHERE status = 'pending'")
        rows = cur.fetchall()
        conn.close()
        return rows
    return await asyncio.to_thread(_get)


async def get_withdrawal(wid):
    def _get():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT * FROM withdrawals WHERE id = ?", (wid,))
        row = cur.fetchone()
        conn.close()
        return row
    return await asyncio.to_thread(_get)


async def update_withdrawal_status(wid, status):
    def _upd():
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE withdrawals SET status = ? WHERE id = ?", (status, wid))
        conn.commit()
        conn.close()
    await asyncio.to_thread(_upd)
