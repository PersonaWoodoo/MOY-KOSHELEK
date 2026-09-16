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
            max_activations INTEGER DEFAULT 1,
            activations INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS check_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(code, user_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            asset TEXT,
            amount REAL,
            address TEXT,
            network TEXT,
            status TEXT DEFAULT 'pending',
            reject_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            asset TEXT,
            amount REAL,
            tx_id TEXT,
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER UNIQUE,
            bonus_paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_bonus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            last_spin TIMESTAMP,
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


def _create_own_check(code, creator_id, target_id, target_username, asset, amount, description, max_activations=1):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO own_checks (code, creator_id, target_id, target_username, asset, amount, description, max_activations) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (code, creator_id, target_id, target_username, asset, amount, description, max_activations)
    )
    conn.commit()
    conn.close()


def _get_own_check(code):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM own_checks WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()
    return row


def _increment_check_activation(code):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE own_checks SET activations = activations + 1 WHERE code = ?", (code,))
    conn.execute("""
        UPDATE own_checks SET status = 'activated'
        WHERE code = ? AND activations >= max_activations
    """, (code,))
    conn.commit()
    conn.close()


def _check_already_activated(code, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT 1 FROM check_activations WHERE code = ? AND user_id = ?", (code, user_id))
    row = cur.fetchone()
    conn.close()
    return row is not None


def _log_check_activation(code, user_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT INTO check_activations (code, user_id) VALUES (?, ?)", (code, user_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def _get_user_by_username(username):
    if not username:
        return None
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM users WHERE LOWER(username) = ?", (username.lower(),))
    row = cur.fetchone()
    conn.close()
    return row


def _reset_economy():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET balance = 0")
    conn.execute("DELETE FROM own_checks")
    conn.execute("DELETE FROM check_activations")
    conn.execute("DELETE FROM withdrawals")
    conn.execute("DELETE FROM deposits")
    conn.commit()
    conn.close()


def _get_user_checks(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT * FROM own_checks WHERE creator_id = ? AND status != 'deleted' ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def _delete_own_check(cid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE own_checks SET status = 'deleted' WHERE id = ?", (cid,))
    conn.commit()
    conn.close()


def _get_own_check_by_id(cid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM own_checks WHERE id = ?", (cid,))
    row = cur.fetchone()
    conn.close()
    return row


def _save_referral(referrer_id, referred_id):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
            (referrer_id, referred_id)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def _get_referral(referred_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM referrals WHERE referred_id = ?", (referred_id,))
    row = cur.fetchone()
    conn.close()
    return row


def _mark_bonus_paid(referred_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE referrals SET bonus_paid = 1 WHERE referred_id = ?", (referred_id,))
    conn.commit()
    conn.close()


def _get_referral_stats(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT COUNT(*), SUM(bonus_paid) FROM referrals WHERE referrer_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def _get_daily_bonus(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM daily_bonus WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def _update_daily_bonus(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO daily_bonus (user_id, last_spin) VALUES (?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET last_spin = CURRENT_TIMESTAMP
    """, (user_id,))
    conn.commit()
    conn.close()


# ===== ВЫВОДЫ =====
def _create_withdrawal_full(user_id, asset, amount, address, network):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO withdrawals (user_id, asset, amount, address, network) VALUES (?, ?, ?, ?, ?)",
        (user_id, asset, amount, address, network)
    )
    wid = cur.lastrowid
    conn.commit()
    conn.close()
    return wid


def _get_withdrawal(wid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM withdrawals WHERE id = ?", (wid,))
    row = cur.fetchone()
    conn.close()
    return row


def _set_withdrawal_status(wid, status, reason=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE withdrawals SET status = ?, reject_reason = ? WHERE id = ?",
        (status, reason, wid)
    )
    conn.commit()
    conn.close()


def _get_pending_withdrawals():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


# ===== ДЕПОЗИТЫ =====
def _create_deposit(user_id, asset, amount, tx_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO deposits (user_id, asset, amount, tx_id) VALUES (?, ?, ?, ?)",
        (user_id, asset, amount, tx_id)
    )
    dep_id = cur.lastrowid
    conn.commit()
    conn.close()
    return dep_id


def _get_deposit(did):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM deposits WHERE id = ?", (did,))
    row = cur.fetchone()
    conn.close()
    return row


def _set_deposit_status(did, status):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE deposits SET status = ? WHERE id = ?", (status, did))
    conn.commit()
    conn.close()


def _get_pending_deposits():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT * FROM deposits WHERE status = 'pending' ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


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


async def create_own_check(code, creator_id, target_id, target_username, asset, amount, description, max_activations=1):
    await asyncio.to_thread(
        _create_own_check, code, creator_id, target_id, target_username,
        asset, amount, description, max_activations
    )


async def get_own_check(code):
    return await asyncio.to_thread(_get_own_check, code)


async def increment_check_activation(code):
    await asyncio.to_thread(_increment_check_activation, code)


async def check_already_activated(code, user_id):
    return await asyncio.to_thread(_check_already_activated, code, user_id)


async def log_check_activation(code, user_id):
    return await asyncio.to_thread(_log_check_activation, code, user_id)


async def get_user_by_username(username):
    return await asyncio.to_thread(_get_user_by_username, username)


async def reset_economy():
    await asyncio.to_thread(_reset_economy)


async def get_user_checks(user_id):
    return await asyncio.to_thread(_get_user_checks, user_id)


async def delete_own_check(cid):
    await asyncio.to_thread(_delete_own_check, cid)


async def get_own_check_by_id(cid):
    return await asyncio.to_thread(_get_own_check_by_id, cid)


async def save_referral(referrer_id, referred_id):
    return await asyncio.to_thread(_save_referral, referrer_id, referred_id)


async def get_referral(referred_id):
    return await asyncio.to_thread(_get_referral, referred_id)


async def mark_bonus_paid(referred_id):
    await asyncio.to_thread(_mark_bonus_paid, referred_id)


async def get_referral_stats(user_id):
    return await asyncio.to_thread(_get_referral_stats, user_id)


async def get_daily_bonus(user_id):
    return await asyncio.to_thread(_get_daily_bonus, user_id)


async def update_daily_bonus(user_id):
    await asyncio.to_thread(_update_daily_bonus, user_id)


async def create_withdrawal_full(user_id, asset, amount, address, network):
    return await asyncio.to_thread(_create_withdrawal_full, user_id, asset, amount, address, network)


async def get_withdrawal(wid):
    return await asyncio.to_thread(_get_withdrawal, wid)


async def set_withdrawal_status(wid, status, reason=""):
    await asyncio.to_thread(_set_withdrawal_status, wid, status, reason)


async def get_pending_withdrawals():
    return await asyncio.to_thread(_get_pending_withdrawals)


async def create_deposit(user_id, asset, amount, tx_id):
    return await asyncio.to_thread(_create_deposit, user_id, asset, amount, tx_id)


async def get_deposit(did):
    return await asyncio.to_thread(_get_deposit, did)


async def set_deposit_status(did, status):
    await asyncio.to_thread(_set_deposit_status, did, status)


async def get_pending_deposits():
    return await asyncio.to_thread(_get_pending_deposits)


async def get_stats():
    def _stats():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT COUNT(*), SUM(amount) FROM own_checks WHERE activations > 0")
        row = cur.fetchone()
        conn.close()
        return row
    return await asyncio.to_thread(_stats)


async def create_withdrawal(user_id, asset, amount, address):
    """Совместимость со старым кодом."""
    return await create_withdrawal_full(user_id, asset, amount, address, asset)


async def update_withdrawal_status(wid, status):
    """Совместимость со старым кодом."""
    await set_withdrawal_status(wid, status)
