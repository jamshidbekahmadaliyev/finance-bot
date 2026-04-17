from datetime import date

import psycopg2
from psycopg2 import Error

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


def get_connection():
    try:
        return psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            sslmode="require",
        )
    except Error as e:
        print(f"[DB] Ulanish xatosi: {e}")
        return None


def create_tables() -> bool:
    conn = get_connection()
    if not conn:
        return False

    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_balance BIGINT NOT NULL DEFAULT 0,
                has_opening_balance BOOLEAN NOT NULL DEFAULT FALSE,
                spend_limit_daily BIGINT,
                reminder_time TEXT NOT NULL DEFAULT '21:00',
                remind_daily BOOLEAN NOT NULL DEFAULT TRUE
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                sana TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tashkent'),
                tur TEXT NOT NULL,
                miqdor BIGINT NOT NULL,
                kategoriya TEXT,
                counterpart TEXT,
                izoh TEXT,
                balance_after BIGINT NOT NULL
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reminder_logs (
                user_id BIGINT NOT NULL REFERENCES users(user_id),
                sent_date DATE NOT NULL,
                PRIMARY KEY (user_id, sent_date)
            );
            """
        )

        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS current_balance BIGINT NOT NULL DEFAULT 0;")
        cur.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS has_opening_balance BOOLEAN NOT NULL DEFAULT FALSE;"
        )
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS spend_limit_daily BIGINT;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS reminder_time TEXT NOT NULL DEFAULT '21:00';")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS remind_daily BOOLEAN NOT NULL DEFAULT TRUE;")

        cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS kategoriya TEXT;")
        cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counterpart TEXT;")
        cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS balance_after BIGINT;")
        cur.execute(
            "ALTER TABLE transactions ALTER COLUMN sana SET DEFAULT (NOW() AT TIME ZONE 'Asia/Tashkent');"
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_trx_user_sana
            ON transactions (user_id, sana DESC);
            """
        )

        conn.commit()
        print("[DB] Jadvallar tayyor.")
        return True
    except Error as e:
        print(f"[DB] Jadval yaratish xatosi: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def check_connection() -> tuple[bool, str]:
    conn = get_connection()
    if not conn:
        return False, "DB ga ulanib bo'lmadi"
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1;")
        cur.fetchone()
        return True, "OK"
    except Error as e:
        return False, str(e)
    finally:
        cur.close()
        conn.close()


def upsert_user(user_id: int, full_name: str, username: str):
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (user_id, full_name, username)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET full_name = EXCLUDED.full_name,
                username = EXCLUDED.username;
            """,
            (user_id, full_name, username),
        )
        conn.commit()
    except Error as e:
        print(f"[DB] upsert_user xatosi: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def get_user_profile(user_id: int) -> dict:
    conn = get_connection()
    if not conn:
        return {
            "current_balance": 0,
            "has_opening_balance": False,
            "spend_limit_daily": None,
            "reminder_time": "21:00",
            "remind_daily": True,
        }
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT current_balance, has_opening_balance, spend_limit_daily, reminder_time, remind_daily
            FROM users
            WHERE user_id = %s;
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return {
                "current_balance": 0,
                "has_opening_balance": False,
                "spend_limit_daily": None,
                "reminder_time": "21:00",
                "remind_daily": True,
            }
        return {
            "current_balance": int(row[0] or 0),
            "has_opening_balance": bool(row[1]),
            "spend_limit_daily": int(row[2]) if row[2] is not None else None,
            "reminder_time": row[3] or "21:00",
            "remind_daily": bool(row[4]),
        }
    except Error as e:
        print(f"[DB] get_user_profile xatosi: {e}")
        return {
            "current_balance": 0,
            "has_opening_balance": False,
            "spend_limit_daily": None,
            "reminder_time": "21:00",
            "remind_daily": True,
        }
    finally:
        cur.close()
        conn.close()


def set_opening_balance(user_id: int, amount: int) -> bool:
    conn = get_connection()
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE users
            SET current_balance = %s,
                has_opening_balance = TRUE
            WHERE user_id = %s;
            """,
            (amount, user_id),
        )
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] set_opening_balance xatosi: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def set_spend_limit_daily(user_id: int, amount: int | None) -> bool:
    conn = get_connection()
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE users
            SET spend_limit_daily = %s
            WHERE user_id = %s;
            """,
            (amount, user_id),
        )
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] set_spend_limit_daily xatosi: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def set_reminder_time(user_id: int, hhmm: str) -> bool:
    conn = get_connection()
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE users
            SET reminder_time = %s
            WHERE user_id = %s;
            """,
            (hhmm, user_id),
        )
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] set_reminder_time xatosi: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def set_remind_daily(user_id: int, enabled: bool) -> bool:
    conn = get_connection()
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE users
            SET remind_daily = %s
            WHERE user_id = %s;
            """,
            (enabled, user_id),
        )
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] set_remind_daily xatosi: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def add_transaction(
    user_id: int,
    tur: str,
    miqdor: int,
    kategoriya: str,
    izoh: str,
    counterpart: str | None = None,
) -> tuple[bool, int, str]:
    conn = get_connection()
    if not conn:
        return False, 0, "DB ulanmagan"

    cur = conn.cursor()
    try:
        cur.execute("SELECT current_balance FROM users WHERE user_id = %s;", (user_id,))
        row = cur.fetchone()
        current_balance = int(row[0] or 0) if row else 0

        if tur in {"kirim", "qarz_oldim"}:
            delta = miqdor
        elif tur in {"chiqim", "qarz_berdim"}:
            delta = -miqdor
        else:
            return False, current_balance, "Noma'lum tur"

        new_balance = current_balance + delta
        if new_balance < 0:
            return False, current_balance, "Balans yetarli emas"

        cur.execute(
            """
            INSERT INTO transactions (user_id, tur, miqdor, kategoriya, counterpart, izoh, balance_after)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            (user_id, tur, miqdor, kategoriya, counterpart, izoh, new_balance),
        )

        cur.execute(
            """
            UPDATE users
            SET current_balance = %s,
                has_opening_balance = TRUE
            WHERE user_id = %s;
            """,
            (new_balance, user_id),
        )

        conn.commit()
        return True, new_balance, "OK"
    except Error as e:
        print(f"[DB] add_transaction xatosi: {e}")
        conn.rollback()
        return False, 0, str(e)
    finally:
        cur.close()
        conn.close()


def get_report(user_id: int, limit: int = 50) -> list:
    conn = get_connection()
    if not conn:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT sana, tur, miqdor, kategoriya, counterpart, izoh, balance_after
            FROM transactions
            WHERE user_id = %s
            ORDER BY sana DESC
            LIMIT %s;
            """,
            (user_id, limit),
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DB] get_report xatosi: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_report_by_range(user_id: int, start_date: str, end_date: str) -> list:
    conn = get_connection()
    if not conn:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT sana, tur, miqdor, kategoriya, counterpart, izoh, balance_after
            FROM transactions
            WHERE user_id = %s
              AND sana::date BETWEEN %s::date AND %s::date
            ORDER BY sana ASC;
            """,
            (user_id, start_date, end_date),
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DB] get_report_by_range xatosi: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_month_report(user_id: int, year: int, month: int) -> list:
    conn = get_connection()
    if not conn:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT sana, tur, miqdor, kategoriya, counterpart, izoh, balance_after
            FROM transactions
            WHERE user_id = %s
              AND EXTRACT(YEAR FROM sana) = %s
              AND EXTRACT(MONTH FROM sana) = %s
            ORDER BY sana ASC;
            """,
            (user_id, year, month),
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DB] get_month_report xatosi: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_summary(user_id: int) -> dict:
    conn = get_connection()
    if not conn:
        return {}
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT tur, COALESCE(SUM(miqdor), 0)
            FROM transactions
            WHERE user_id = %s
            GROUP BY tur;
            """,
            (user_id,),
        )
        rows = {r[0]: int(r[1] or 0) for r in cur.fetchall()}

        cur.execute("SELECT current_balance FROM users WHERE user_id = %s;", (user_id,))
        bal_row = cur.fetchone()

        kirim = rows.get("kirim", 0)
        chiqim = rows.get("chiqim", 0)
        qarz_berdim = rows.get("qarz_berdim", 0)
        qarz_oldim = rows.get("qarz_oldim", 0)
        return {
            "kirim": kirim,
            "chiqim": chiqim,
            "qarz_berdim": qarz_berdim,
            "qarz_oldim": qarz_oldim,
            "sof_operatsion": kirim - chiqim,
            "qarz_saldo": qarz_berdim - qarz_oldim,
            "current_balance": int(bal_row[0] or 0) if bal_row else 0,
        }
    except Error as e:
        print(f"[DB] get_summary xatosi: {e}")
        return {}
    finally:
        cur.close()
        conn.close()


def get_loans_by_person(user_id: int) -> list:
    conn = get_connection()
    if not conn:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                COALESCE(NULLIF(TRIM(counterpart), ''), 'noma\'lum') AS person,
                COALESCE(SUM(CASE WHEN tur = 'qarz_berdim' THEN miqdor ELSE 0 END), 0) AS bergan,
                COALESCE(SUM(CASE WHEN tur = 'qarz_oldim' THEN miqdor ELSE 0 END), 0) AS olgan
            FROM transactions
            WHERE user_id = %s AND tur IN ('qarz_berdim', 'qarz_oldim')
            GROUP BY COALESCE(NULLIF(TRIM(counterpart), ''), 'noma\'lum')
            ORDER BY person;
            """,
            (user_id,),
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DB] get_loans_by_person xatosi: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_spent_today(user_id: int) -> int:
    conn = get_connection()
    if not conn:
        return 0
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(miqdor), 0)
            FROM transactions
            WHERE user_id = %s
              AND tur = 'chiqim'
              AND sana::date = (NOW() AT TIME ZONE 'Asia/Tashkent')::date;
            """,
            (user_id,),
        )
        return int(cur.fetchone()[0] or 0)
    except Error as e:
        print(f"[DB] get_spent_today xatosi: {e}")
        return 0
    finally:
        cur.close()
        conn.close()


def get_daily_expense_series(user_id: int, days: int = 30) -> list:
    conn = get_connection()
    if not conn:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT day::date, COALESCE(SUM(t.miqdor), 0) AS expense
            FROM generate_series(
                (NOW() AT TIME ZONE 'Asia/Tashkent')::date - (%s - 1),
                (NOW() AT TIME ZONE 'Asia/Tashkent')::date,
                interval '1 day'
            ) AS day
            LEFT JOIN transactions t
              ON t.user_id = %s
             AND t.tur = 'chiqim'
             AND t.sana::date = day::date
            GROUP BY day
            ORDER BY day;
            """,
            (days, user_id),
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DB] get_daily_expense_series xatosi: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def list_users_for_daily_reminder() -> list:
    conn = get_connection()
    if not conn:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id, reminder_time, remind_daily, spend_limit_daily, current_balance
            FROM users;
            """
        )
        return cur.fetchall()
    except Error as e:
        print(f"[DB] list_users_for_daily_reminder xatosi: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def is_reminder_sent_today(user_id: int, day: date) -> bool:
    conn = get_connection()
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM reminder_logs WHERE user_id = %s AND sent_date = %s;
            """,
            (user_id, day),
        )
        return cur.fetchone() is not None
    except Error as e:
        print(f"[DB] is_reminder_sent_today xatosi: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def mark_reminder_sent_today(user_id: int, day: date) -> bool:
    conn = get_connection()
    if not conn:
        return False
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO reminder_logs (user_id, sent_date)
            VALUES (%s, %s)
            ON CONFLICT (user_id, sent_date) DO NOTHING;
            """,
            (user_id, day),
        )
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] mark_reminder_sent_today xatosi: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()
