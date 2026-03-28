# =====================================================
# db.py — Ma'lumotlar bazasi bilan ishlash
# =====================================================
# Bu fayl Supabase (PostgreSQL) ga ulanadi va
# har bir foydalanuvchini user_id orqali ajratadi.

import psycopg2
from psycopg2 import Error
from config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT


# --------------------------------------------------
# Ulanish funksiyasi
# --------------------------------------------------
def get_connection():
    """Supabase ga ulanish qaytaradi."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            sslmode="require"       # Supabase SSL talab qiladi
        )
        return conn
    except Error as e:
        print(f"[DB] Ulanish xatosi: {e}")
        return None


# --------------------------------------------------
# Jadval yaratish (faqat birinchi ishga tushganda)
# --------------------------------------------------
def create_tables():
    """
    Ikki jadval yaratadi:
      1. users       — foydalanuvchi haqida ma'lumot
      2. transactions — har bir kirim/chiqim yozuvi
    """
    conn = get_connection()
    if not conn:
        return

    cur = conn.cursor()
    try:
        # Foydalanuvchilar jadvali
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     BIGINT PRIMARY KEY,
                full_name   TEXT,
                username    TEXT,
                joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Tranzaksiyalar jadvali
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id                  SERIAL PRIMARY KEY,
                user_id             BIGINT NOT NULL REFERENCES users(user_id),
                sana                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tur                 TEXT NOT NULL,
                -- tur: 'kirim' | 'chiqim' | 'qarz_berdim' | 'qarz_oldim'
                miqdor              BIGINT NOT NULL DEFAULT 0,
                izoh                TEXT
            );
        """)

        conn.commit()
        print("[DB] Jadvallar tayyor.")
    except Error as e:
        print(f"[DB] Jadval yaratish xatosi: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# --------------------------------------------------
# Foydalanuvchini saqlash yoki yangilash
# --------------------------------------------------
def upsert_user(user_id: int, full_name: str, username: str):
    """
    Foydalanuvchi birinchi marta yozganda uni bazaga qo'shadi.
    Agar avval qo'shilgan bo'lsa, yangilaydi (ismi o'zgarishi mumkin).
    """
    conn = get_connection()
    if not conn:
        return

    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (user_id, full_name, username)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
                SET full_name = EXCLUDED.full_name,
                    username  = EXCLUDED.username;
        """, (user_id, full_name, username))
        conn.commit()
    except Error as e:
        print(f"[DB] Foydalanuvchi saqlash xatosi: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# --------------------------------------------------
# Tranzaksiya qo'shish
# --------------------------------------------------
def add_transaction(user_id: int, tur: str, miqdor: int, izoh: str = None) -> bool:
    """
    Yangi yozuv qo'shadi.
    tur: 'kirim' | 'chiqim' | 'qarz_berdim' | 'qarz_oldim'
    """
    conn = get_connection()
    if not conn:
        return False

    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO transactions (user_id, tur, miqdor, izoh)
            VALUES (%s, %s, %s, %s);
        """, (user_id, tur, miqdor, izoh))
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] Tranzaksiya qo'shish xatosi: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


# --------------------------------------------------
# Oxirgi N ta tranzaksiyani olish (report uchun)
# --------------------------------------------------
def get_report(user_id: int, limit: int = 10) -> list:
    """
    Foydalanuvchining oxirgi `limit` ta yozuvini qaytaradi.
    """
    conn = get_connection()
    if not conn:
        return []

    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT sana, tur, miqdor, izoh
            FROM transactions
            WHERE user_id = %s
            ORDER BY sana DESC
            LIMIT %s;
        """, (user_id, limit))
        return cur.fetchall()
    except Error as e:
        print(f"[DB] Report xatosi: {e}")
        return []
    finally:
        cur.close()
        conn.close()


# --------------------------------------------------
# Umumiy statistika (analiz uchun)
# --------------------------------------------------
def get_stats(user_id: int) -> dict:
    """
    Foydalanuvchining umumiy kirim/chiqim/qarz summalarini qaytaradi.
    """
    conn = get_connection()
    if not conn:
        return {}

    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT tur, SUM(miqdor)
            FROM transactions
            WHERE user_id = %s
            GROUP BY tur;
        """, (user_id,))
        rows = cur.fetchall()
        # { 'kirim': 1500000, 'chiqim': 300000, ... }
        return {row[0]: row[1] for row in rows}
    except Error as e:
        print(f"[DB] Statistika xatosi: {e}")
        return {}
    finally:
        cur.close()
        conn.close()


# --------------------------------------------------
# Oxirgi N kunlik hisobot
# --------------------------------------------------
def get_stats_by_days(user_id: int, kunlar: int = 30) -> dict:
    """
    So'nggi `kunlar` kun ichidagi statistikani qaytaradi.
    """
    conn = get_connection()
    if not conn:
        return {}

    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT tur, SUM(miqdor)
            FROM transactions
            WHERE user_id = %s
              AND sana >= NOW() - INTERVAL '%s days'
            GROUP BY tur;
        """, (user_id, kunlar))
        rows = cur.fetchall()
        return {row[0]: row[1] for row in rows}
    except Error as e:
        print(f"[DB] Kunlik statistika xatosi: {e}")
        return {}
    finally:
        cur.close()
        conn.close()
