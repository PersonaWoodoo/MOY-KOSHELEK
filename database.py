# ========== МОИ ЧЕКИ ==========
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


async def get_user_checks(user_id):
    return await asyncio.to_thread(_get_user_checks, user_id)


async def delete_own_check(cid):
    await asyncio.to_thread(_delete_own_check, cid)


async def get_own_check_by_id(cid):
    return await asyncio.to_thread(_get_own_check_by_id, cid)
