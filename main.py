#!/usr/bin/env python3
"""
💎 TRX EDITION PREMIUM BOT - OSINT LOOKUP (v2.2 HTML-FIX)
Channel-join verification + Premium menu + All API features
"""

import re
import time
import html
import requests
import json
import logging
import asyncio
import sqlite3
import threading
import secrets
import os
import csv
import tempfile
from flask import Flask, jsonify
from datetime import datetime, timedelta, timezone
IST = timezone(timedelta(hours=5, minutes=30))

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.error import BadRequest, Forbidden, RetryAfter
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ChatMemberHandler, ContextTypes, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ══════════════ CONFIG ══════════════
BOT_TOKEN = "7041790426:AAHOKgc2Au90maW8ZSynCCoxjDZD38z8nro"
API_URL = "https://api-src.alonepatel.shop/api"
API_KEY = "INDIAN_HACKER_BRO"

API_KEY_OVERRIDES = {
    "tgid": "Tgid_num"
}
CHANNEL_ID = "@TRX_EDITION_VIP"
CHANNEL_LINK = "https://t.me/TRX_EDITION_VIP"

# ================= ADMIN CONFIG =================

ADMIN_IDS = {5453397878}

BANNED_USERS = set()

# =====================================================
# 🛡️ PROTECTED DATA CONFIG
# =====================================================
PROTECTED_IDS = {
    "5453397878",
    "5057489358",
    "9876543210",
}
PROTECTED_USERNAMES = {
    "INDIANHACKER4",
    "@theplayerror",
    "another_user",
}
PROTECTED_NUMBERS = {
    "7001880266",
    "+917001880266",
    "8101851498",
    "+918101851498",
}
PROTECTION_MESSAGE = (
    "🛡️ <b>PROTECTED DATA</b>\n\n"
    "This information is protected and cannot be accessed.\n\n"
    "🔐 <b>Protection by @INDIANHACKER4</b>\n"
    "🛡️ Protect your data\n"
    "📩 Contact: @INDIANHACKER4"
)
REQUEST_COUNT = 0
MAINTENANCE_MODE = False

# =========================================================
# ADMIN NOTIFICATION
# =========================================================




# Rate limit
LAST_REQUEST = {}
REQUEST_COOLDOWN = 3

# Recent activity
ACTIVITY_LOGS = []
USER_IDS = set()

# ── LightSpeed runtime metrics ──
API_METRICS = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "total_ms": 0.0,
    "last_ms": 0.0,
    "last_status": "UNKNOWN",
    "last_action": "-",
    "last_check": 0.0,
}
API_METRICS_LOCK = threading.Lock()

HEALTH_STATE = {
    "status": "UNKNOWN",
    "latency_ms": None,
    "http_status": None,
    "checked_at": 0.0,
}

# ═════════════════════════════════════════════════════════════
# 🌐 RENDER / FLASK WEB SERVER
# Render Web Services require an HTTP listener on 0.0.0.0:$PORT.
# The Telegram bot continues running in this same process.
# ═════════════════════════════════════════════════════════════
WEB_APP = Flask(__name__)
WEB_PORT = int(os.getenv("PORT", "10000"))


@WEB_APP.get("/")
def web_home():
    return jsonify({
        "service": "TRX EDITION PREMIUM BOT",
        "status": "online",
        "message": "Telegram bot process is running.",
        "uptime_seconds": int(max(0, time.time() - START_TIME)),
    })


@WEB_APP.get("/health")
def web_health():
    health = dict(HEALTH_STATE)
    return jsonify({
        "status": "ok",
        "bot": "running",
        "api": health.get("status", "UNKNOWN"),
        "api_latency_ms": health.get("latency_ms"),
        "api_http_status": health.get("http_status"),
        "uptime_seconds": int(max(0, time.time() - START_TIME)),
    }), 200


@WEB_APP.get("/ping")
def web_ping():
    return "pong", 200


def start_web_server():
    """Start the Flask health server in a daemon thread for Render."""
    def _run():
        try:
            logger.info("Render web server listening on 0.0.0.0:%s", WEB_PORT)
            WEB_APP.run(
                host="0.0.0.0",
                port=WEB_PORT,
                debug=False,
                use_reloader=False,
                threaded=True,
            )
        except Exception:
            logger.exception("Render web server stopped unexpectedly")

    thread = threading.Thread(
        target=_run,
        name="render-web-server",
        daemon=True,
    )
    thread.start()
    return thread


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def add_log(user_id: int, action: str):
    log_time = time.strftime("%Y-%m-%d %H:%M:%S")

    ACTIVITY_LOGS.append({
        "user_id": user_id,
        "action": action,
        "time": log_time
    })

    if len(ACTIVITY_LOGS) > 100:
        ACTIVITY_LOGS.pop(0)

    db_add_log(user_id, action)
        
        
# ── Headers (403 bypass) ──
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://api-src.alonepatel.shop/",
}

# ── Runtime state ──
VERIFIED_USERS = set()
START_TIME = time.time()

# ── SQLite persistence ──
DB_FILE = "bot.db"
DB_LOCK = threading.Lock()


def init_db():
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_seen REAL NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_groups (
                chat_id INTEGER PRIMARY KEY,
                title TEXT,
                first_seen REAL NOT NULL
            )
        """)

        for column, definition in (("username", "TEXT"), ("first_name", "TEXT"), ("referrer_id", "INTEGER"), ("referral_rewarded", "INTEGER NOT NULL DEFAULT 0"), ("referral_count", "INTEGER NOT NULL DEFAULT 0")):
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass

        cur.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL UNIQUE,
                created_at REAL NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS protected_entries (
                value TEXT PRIMARY KEY,
                entry_type TEXT NOT NULL,
                created_at REAL NOT NULL,
                added_by INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                banned_at REAL NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS verified_users (
                user_id INTEGER PRIMARY KEY,
                verified_at REAL NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                log_time TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
        """)

        cur.execute("""
            INSERT OR IGNORE INTO stats(key, value)
            VALUES('request_count', 0)
        """)
        
        # ══════════════════════════════
        # WALLET SYSTEM
        # ══════════════════════════════

        cur.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                user_id INTEGER PRIMARY KEY,
                credits INTEGER NOT NULL DEFAULT 0,
                bonus_credits INTEGER NOT NULL DEFAULT 0,
                spins INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL
            )
        """)

        # ══════════════════════════════
        # SUBSCRIPTIONS
        # ══════════════════════════════

        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                started_at REAL NOT NULL,
                expires_at REAL,
                status TEXT NOT NULL DEFAULT 'active',
                payment_ref TEXT
            )
        """)
        
        # ══════════════════════════════
        # SUBSCRIPTION EXPIRY NOTIFICATIONS
        # ══════════════════════════════

        cur.execute("""
            CREATE TABLE IF NOT EXISTS expiry_notifications (
                subscription_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                notified_at REAL NOT NULL
            )
        """)

        # ══════════════════════════════
        # CREDIT TRANSACTIONS
        # ══════════════════════════════

        cur.execute("""
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                tx_type TEXT NOT NULL,
                note TEXT,
                created_at REAL NOT NULL
            )
        """)

        # ══════════════════════════════
        # SPIN HISTORY
        # ══════════════════════════════

        cur.execute("""
            CREATE TABLE IF NOT EXISTS spin_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                reward_type TEXT NOT NULL,
                reward_value INTEGER NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'INR',
                status TEXT NOT NULL DEFAULT 'pending',
                provider TEXT,
                provider_ref TEXT,
                created_at REAL NOT NULL
            )
        """)
        
        try:
          cur.execute(
          "ALTER TABLE wallets ADD COLUMN last_spin_date TEXT"
          )
        except sqlite3.OperationalError:
          pass
          
        try:
          cur.execute(
          "ALTER TABLE wallets ADD COLUMN last_daily_credit_date TEXT"
          )
        except sqlite3.OperationalError:
          pass

        try:
          cur.execute(
          "ALTER TABLE wallets ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0"
          )
        except sqlite3.OperationalError:
          pass
    
        
        conn.commit()
        conn.close()



# ══════════════════════════════════════
# 💎 SUBSCRIPTION PLANS
# ══════════════════════════════════════

PLANS = {
    "free": {
        "name": "🆓 FREE",
        "duration_days": None,
        "credits": 5,
        "daily_credits": 2,
        "price": 0,
    },

    "vip": {
        "name": "⭐ VIP",
        "duration_days": 30,
        "credits": 100,
        "daily_credits": 5,
        "price": 99,
    },

    "premium": {
        "name": "💎 PREMIUM",
        "duration_days": 30,
        "credits": 300,
        "daily_credits": 10,
        "price": 199,
    },

    "lifetime": {
        "name": "♾️ LIFETIME",
        "duration_days": None,
        "credits": 1000,
        "daily_credits": 20,
        "price": 499,
    },
}

# ══════════════════════════════════════
# 💳 SAFE SERVICE CREDIT COST
# ══════════════════════════════════════

BILLABLE_SAFE_ACTIONS = {
    "num": 1,
    "aadhar": 1,
    "tg": 1,
    "tgid_num": 1,
    "insta": 1,
    "imei": 1,
    "pin": 1,
    "ifsc": 1,
    "country": 1,
    "upi": 1,
    "paytm": 1,

    "v1": 1,
    "v2": 1,
    "v3": 1,
    "v4": 1,

    "ipv1": 1,
    "ipv2": 1,
    "ipv3": 1,

    "weather": 1,
    "weatherinfo": 1,
}



# ══════════════════════════════════════
# 💳 WALLET FUNCTIONS
# ══════════════════════════════════════

def ensure_wallet(user_id):
    now = time.time()

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        conn.execute("""
            INSERT OR IGNORE INTO wallets
            (user_id, credits, bonus_credits, spins, updated_at)
            VALUES (?, 0, 0, 1, ?)
        """, (user_id, now))

        conn.commit()
        conn.close()


def get_wallet(user_id):
    ensure_wallet(user_id)

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        cur = conn.execute("""
            SELECT credits, bonus_credits, spins, daily_streak
            FROM wallets
            WHERE user_id = ?
        """, (user_id,))

        row = cur.fetchone()
        conn.close()

    if not row:
        return {
            "credits": 0,
            "bonus_credits": 0,
            "spins": 0,
            "daily_streak": 0
        }

    return {
        "credits": row[0],
        "bonus_credits": row[1],
        "spins": row[2],
        "daily_streak": row[3] or 0
    }

def add_credits(user_id, amount, tx_type="bonus", note=""):
    if amount <= 0:
        return False

    ensure_wallet(user_id)

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        conn.execute("""
            UPDATE wallets
            SET credits = credits + ?,
                updated_at = ?
            WHERE user_id = ?
        """, (
            amount,
            time.time(),
            user_id
        ))

        cur = conn.execute("""
            SELECT credits
            FROM wallets
            WHERE user_id = ?
        """, (user_id,))

        row = cur.fetchone()

        if not row:
            conn.rollback()
            conn.close()
            return False

        balance = row[0]

        conn.execute("""
            INSERT INTO credit_transactions
            (
                user_id,
                amount,
                balance_after,
                tx_type,
                note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            amount,
            balance,
            tx_type,
            note,
            time.time()
        ))

        conn.commit()
        conn.close()

    return True



def spend_credits(user_id, amount, note=""):
    if amount <= 0:
        return False

    ensure_wallet(user_id)

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        try:
            conn.execute("BEGIN IMMEDIATE")

            cur = conn.execute("""
                SELECT credits
                FROM wallets
                WHERE user_id = ?
            """, (user_id,))

            row = cur.fetchone()

            if not row:
                conn.rollback()
                return False

            current_balance = row[0]

            if current_balance < amount:
                conn.rollback()
                return False

            new_balance = current_balance - amount

            conn.execute("""
                UPDATE wallets
                SET credits = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                new_balance,
                time.time(),
                user_id
            ))

            conn.execute("""
                INSERT INTO credit_transactions
                (
                    user_id,
                    amount,
                    balance_after,
                    tx_type,
                    note,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                -amount,
                new_balance,
                "usage",
                note,
                time.time()
            ))

            conn.commit()
            return True

        except Exception:
            conn.rollback()
            logger.exception("Credit deduction failed")
            return False

        finally:
            conn.close()


def refund_credits(user_id, amount, note="Service failed - refund"):
    return add_credits(
        user_id,
        amount,
        tx_type="refund",
        note=note
    )


# =====================================================
# 👑 ADMIN: MANUALLY GIVE SUBSCRIPTION PLAN
# Usage: /addplan USER_ID vip
#        /addplan USER_ID premium
#        /addplan USER_ID lifetime
# =====================================================

async def addplan_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    admin_id = update.effective_user.id

    if not is_admin(admin_id):
        await update.message.reply_text(
            "⛔ <b>ACCESS DENIED</b>",
            parse_mode="HTML"
        )
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ <b>Wrong format</b>\n\n"
            "Use:\n"
            "<code>/addplan USER_ID PLAN</code>\n\n"
            "Plans:\n"
            "• <code>vip</code>\n"
            "• <code>premium</code>\n"
            "• <code>lifetime</code>\n\n"
            "Example:\n"
            "<code>/addplan 123456789 premium</code>",
            parse_mode="HTML"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid Telegram User ID.",
            parse_mode="HTML"
        )
        return

    plan_id = context.args[1].lower().strip()

    if plan_id not in PLANS:
        await update.message.reply_text(
            "❌ Invalid plan.\n\n"
            "Available: <code>vip</code>, "
            "<code>premium</code>, "
            "<code>lifetime</code>",
            parse_mode="HTML"
        )
        return

    plan = PLANS[plan_id]
    now = time.time()

    days = plan["duration_days"]

    if days is None:
        expires_at = None
        expiry_text = "♾️ Lifetime"
    else:
        expires_at = now + (int(days) * 86400)
        expiry_text = (
            datetime.fromtimestamp(
                expires_at,
                tz=IST
            ).strftime("%d-%m-%Y %H:%M")
        )

    try:
        with DB_LOCK:
            conn = sqlite3.connect(DB_FILE)

            # Old active plan expire
            conn.execute("""
                UPDATE subscriptions
                SET status = 'expired'
                WHERE user_id = ?
                  AND status = 'active'
            """, (target_id,))

            # New plan
            conn.execute("""
                INSERT INTO subscriptions
                (
                    user_id,
                    plan,
                    started_at,
                    expires_at,
                    status,
                    payment_ref
                )
                VALUES (?, ?, ?, ?, 'active', ?)
            """, (
                target_id,
                plan_id,
                now,
                expires_at,
                "ADMIN-GRANT"
            ))

            # Make sure wallet exists
            conn.execute("""
                INSERT OR IGNORE INTO wallets
                (
                    user_id,
                    credits,
                    bonus_credits,
                    spins,
                    updated_at
                )
                VALUES (?, 0, 0, 1, ?)
            """, (
                target_id,
                now
            ))

            # Starting plan credits
            starting_credits = int(plan["credits"])

            conn.execute("""
                UPDATE wallets
                SET credits = credits + ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                starting_credits,
                now,
                target_id
            ))

            conn.commit()
            conn.close()

        await update.message.reply_text(
            "✅ <b>PLAN ACTIVATED</b>\n\n"
            f"👤 User ID: <code>{target_id}</code>\n"
            f"💎 Plan: <b>{html.escape(str(plan['name']))}</b>\n"
            f"🎟️ Added Credits: <b>{starting_credits}</b>\n"
            f"🎁 Daily Credits: <b>{plan['daily_credits']}</b>\n"
            f"⏰ Expiry: <b>{expiry_text}</b>",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.exception("Admin plan grant failed")

        await update.message.reply_text(
            "❌ Failed to activate plan.\n"
            "Check the bot logs.",
            parse_mode="HTML"
        )



# ══════════════════════════════════════
# ⏰ SUBSCRIPTION EXPIRY REMINDER SYSTEM
# ══════════════════════════════════════

async def send_expiry_reminders(application):

    now = time.time()

    # আগামী 24 ঘণ্টার মধ্যে expire হবে এমন active subscriptions
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        rows = conn.execute("""
            SELECT
                s.id,
                s.user_id,
                s.plan,
                s.expires_at
            FROM subscriptions s
            LEFT JOIN expiry_notifications e
                ON e.subscription_id = s.id
            WHERE s.status = 'active'
              AND s.expires_at IS NOT NULL
              AND s.expires_at > ?
              AND s.expires_at <= ?
              AND e.subscription_id IS NULL
        """, (
            now,
            now + 86400
        )).fetchall()

        conn.close()

    for subscription_id, user_id, plan, expires_at in rows:

        try:

            expiry_text = datetime.fromtimestamp(
                expires_at,
                IST
            ).strftime("%d-%m-%Y %H:%M")

            message = (
                "⏰ <b>SUBSCRIPTION EXPIRY REMINDER</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 Plan: <b>{html.escape(str(plan).upper())}</b>\n"
                f"⏳ Expiry: <b>{expiry_text}</b>\n\n"
                "⚠️ Your subscription will expire within "
                "<b>24 hours</b>.\n\n"
                "💎 Renew your plan to continue using "
                "premium features.\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="HTML"
            )

            # Successfully sent হলে database-এ mark করা হবে
            with DB_LOCK:
                conn = sqlite3.connect(DB_FILE)

                conn.execute("""
                    INSERT OR REPLACE INTO expiry_notifications
                    (
                        subscription_id,
                        user_id,
                        notified_at
                    )
                    VALUES (?, ?, ?)
                """, (
                    subscription_id,
                    user_id,
                    time.time()
                ))

                conn.commit()
                conn.close()

        except Forbidden:

            logger.info(
                "Expiry reminder: user %s blocked the bot.",
                user_id
            )

        except Exception:

            logger.exception(
                "Expiry reminder failed for user %s",
                user_id
            )


async def expiry_reminder_loop(application):

    while True:

        try:

            await send_expiry_reminders(
                application
            )

        except Exception:

            logger.exception(
                "Expiry reminder loop failed"
            )

        # প্রতি 30 মিনিটে check করবে
        await asyncio.sleep(1800)


def get_user_plan(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        cur = conn.execute("""
            SELECT plan, expires_at
            FROM subscriptions
            WHERE user_id = ?
            AND status = 'active'
            ORDER BY id DESC
            LIMIT 1
        """, (user_id,))

        row = cur.fetchone()
        conn.close()

    if not row:
        return "free", None

    plan, expires_at = row

    if expires_at is not None:
        if expires_at <= time.time():
            return "free", None

    if plan not in PLANS:
        return "free", None

    return plan, expires_at

def approve_payment(payment_id):
    """
    Atomically approve one pending payment and activate its plan.

    Returns:
        (success, status, user_id, plan_id)
    """

    now = time.time()
    payment_ref = f"PAY-{payment_id}"

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE, timeout=10)

        try:
            conn.execute("BEGIN IMMEDIATE")

            # =================================================
            # PAYMENT CHECK
            # =================================================
            row = conn.execute("""
                SELECT user_id, plan, amount, status
                FROM payments
                WHERE id = ?
            """, (payment_id,)).fetchone()

            if not row:
                conn.rollback()
                return False, "not_found", None, None

            user_id, plan_id, amount, status = row

            # =================================================
            # ALREADY PROCESSED
            # =================================================
            if status != "pending":
                conn.rollback()
                return False, status, user_id, plan_id

            # =================================================
            # PLAN VALIDATION
            # =================================================
            if plan_id not in PLANS:
                conn.rollback()

                logger.error(
                    "Invalid plan '%s' for payment %s",
                    plan_id,
                    payment_id
                )

                return False, "invalid_plan", user_id, plan_id

            plan = PLANS[plan_id]

            # =================================================
            # AMOUNT VALIDATION
            #
            # Database-এর payment amount আর plan price
            # match করছে কিনা check
            # =================================================
            expected_amount = float(plan["price"])

            try:
                payment_amount = float(amount)
            except (TypeError, ValueError):
                conn.rollback()

                logger.error(
                    "Invalid payment amount for payment %s",
                    payment_id
                )

                return False, "invalid_amount", user_id, plan_id

            if payment_amount != expected_amount:
                conn.rollback()

                logger.error(
                    "Payment amount mismatch: payment=%s "
                    "amount=%s expected=%s",
                    payment_id,
                    payment_amount,
                    expected_amount
                )

                return False, "amount_mismatch", user_id, plan_id

            # =================================================
            # PAYMENT REF DUPLICATE CHECK
            # =================================================
            existing_subscription = conn.execute("""
                SELECT id
                FROM subscriptions
                WHERE payment_ref = ?
                LIMIT 1
            """, (payment_ref,)).fetchone()

            if existing_subscription:
                conn.rollback()

                return False, "already_processed", user_id, plan_id

            # =================================================
            # MARK PAYMENT APPROVED
            # =================================================
            cur = conn.execute("""
                UPDATE payments
                SET status = 'approved',
                    provider_ref = ?
                WHERE id = ?
                  AND status = 'pending'
            """, (
                payment_ref,
                payment_id
            ))

            if cur.rowcount != 1:
                conn.rollback()

                return False, "already_processed", user_id, plan_id

            # =================================================
            # OLD ACTIVE SUBSCRIPTION EXPIRE
            # =================================================
            conn.execute("""
                UPDATE subscriptions
                SET status = 'expired'
                WHERE user_id = ?
                  AND status = 'active'
            """, (user_id,))

            # =================================================
            # NEW SUBSCRIPTION
            # =================================================
            days = plan["duration_days"]

            expires_at = None

            if days is not None:
                expires_at = now + (
                    int(days) * 86400
                )

            conn.execute("""
                INSERT INTO subscriptions
                (
                    user_id,
                    plan,
                    started_at,
                    expires_at,
                    status,
                    payment_ref
                )
                VALUES (?, ?, ?, ?, 'active', ?)
            """, (
                user_id,
                plan_id,
                now,
                expires_at,
                payment_ref
            ))

            # =================================================
            # WALLET CREATE IF NEEDED
            # =================================================
            conn.execute("""
                INSERT OR IGNORE INTO wallets
                (
                    user_id,
                    credits,
                    bonus_credits,
                    spins,
                    updated_at
                )
                VALUES (?, 0, 0, 1, ?)
            """, (
                user_id,
                now
            ))

            # =================================================
            # STARTING CREDITS
            # =================================================
            starting_credits = int(
                plan["credits"]
            )

            wallet_row = conn.execute("""
                SELECT credits
                FROM wallets
                WHERE user_id = ?
            """, (user_id,)).fetchone()

            if not wallet_row:
                conn.rollback()

                logger.error(
                    "Wallet not found after INSERT OR IGNORE "
                    "for user %s",
                    user_id
                )

                return False, "wallet_error", user_id, plan_id

            old_balance = int(wallet_row[0])
            new_balance = old_balance + starting_credits

            conn.execute("""
                UPDATE wallets
                SET credits = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                new_balance,
                now,
                user_id
            ))

            # =================================================
            # CREDIT TRANSACTION
            # =================================================
            if starting_credits > 0:
                conn.execute("""
                    INSERT INTO credit_transactions
                    (
                        user_id,
                        amount,
                        balance_after,
                        tx_type,
                        note,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    starting_credits,
                    new_balance,
                    "plan_bonus",
                    f"{plan_id} plan payment #{payment_id}",
                    now
                ))

            # =================================================
            # COMMIT EVERYTHING TOGETHER
            # =================================================
            conn.commit()

            logger.info(
                "Payment approved: payment=%s user=%s plan=%s",
                payment_id,
                user_id,
                plan_id
            )

            return True, "approved", user_id, plan_id

        except Exception:
            conn.rollback()

            logger.exception(
                "Payment approval failed for payment %s",
                payment_id
            )

            return False, "error", None, None

        finally:
            conn.close()



def activate_plan(user_id, plan, days=None, payment_ref=None):
    if plan not in PLANS:
        return False

    # FREE plan বারবার activate করে credit নেওয়া বন্ধ
    if plan == "free":
        current_plan, _ = get_user_plan(user_id)
        if current_plan != "free":
            return False

    now = time.time()

    if days is None:
        days = PLANS[plan]["duration_days"]

    expires_at = None
    if days is not None:
        expires_at = now + (days * 86400)

    starting_credits = PLANS[plan]["credits"]

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        try:
            conn.execute("BEGIN IMMEDIATE")

            # একই payment_ref আগে ব্যবহার হয়েছে কিনা
            if payment_ref:
                existing = conn.execute("""
                    SELECT id
                    FROM subscriptions
                    WHERE payment_ref = ?
                    LIMIT 1
                """, (payment_ref,)).fetchone()

                if existing:
                    conn.rollback()
                    return False

            # পুরোনো active subscription বন্ধ
            conn.execute("""
                UPDATE subscriptions
                SET status = 'expired'
                WHERE user_id = ?
                AND status = 'active'
            """, (user_id,))

            # নতুন subscription
            conn.execute("""
                INSERT INTO subscriptions
                (
                    user_id,
                    plan,
                    started_at,
                    expires_at,
                    status,
                    payment_ref
                )
                VALUES (?, ?, ?, ?, 'active', ?)
            """, (
                user_id,
                plan,
                now,
                expires_at,
                payment_ref
            ))

            # Wallet নিশ্চিত করা
            conn.execute("""
                INSERT OR IGNORE INTO wallets
                (
                    user_id,
                    credits,
                    bonus_credits,
                    spins,
                    updated_at
                )
                VALUES (?, 0, 0, 1, ?)
            """, (user_id, now))

            # Starting credits
            if starting_credits > 0:
                cur = conn.execute("""
                    SELECT credits
                    FROM wallets
                    WHERE user_id = ?
                """, (user_id,))

                row = cur.fetchone()

                if not row:
                    conn.rollback()
                    return False

                new_balance = row[0] + starting_credits

                conn.execute("""
                    UPDATE wallets
                    SET credits = ?,
                        updated_at = ?
                    WHERE user_id = ?
                """, (
                    new_balance,
                    now,
                    user_id
                ))

                conn.execute("""
                    INSERT INTO credit_transactions
                    (
                        user_id,
                        amount,
                        balance_after,
                        tx_type,
                        note,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    starting_credits,
                    new_balance,
                    "plan_bonus",
                    f"{plan} plan activation",
                    now
                ))

            conn.commit()
            return True

        except Exception:
            conn.rollback()
            logger.exception("Plan activation failed")
            return False

        finally:
            conn.close()


def create_payment_request(user_id, plan, amount=0):
    # =========================================================
    # PLAN VALIDATION
    # =========================================================
    if plan not in PLANS:
        return None

    expected_amount = float(
        PLANS[plan]["price"]
    )

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = expected_amount

    # Security/consistency:
    # caller-এর amount আর plan price match না করলে
    # actual plan price ব্যবহার করা হবে।
    if amount != expected_amount:
        amount = expected_amount

    with DB_LOCK:
        conn = sqlite3.connect(
            DB_FILE,
            timeout=10
        )

        try:
            conn.execute("BEGIN IMMEDIATE")

            # =================================================
            # EXISTING PENDING REQUEST CHECK
            # =================================================
            existing = conn.execute("""
                SELECT id
                FROM payments
                WHERE user_id = ?
                  AND plan = ?
                  AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
            """, (
                user_id,
                plan
            )).fetchone()

            if existing:
                conn.commit()
                return existing[0]

            # =================================================
            # CREATE NEW PAYMENT REQUEST
            # =================================================
            cur = conn.execute("""
                INSERT INTO payments
                (
                    user_id,
                    plan,
                    amount,
                    currency,
                    status,
                    provider,
                    created_at
                )
                VALUES (
                    ?, ?, ?, 'INR',
                    'pending',
                    'manual',
                    ?
                )
            """, (
                user_id,
                plan,
                amount,
                time.time()
            ))

            payment_id = cur.lastrowid

            conn.commit()

            logger.info(
                "Payment request created: payment=%s "
                "user=%s plan=%s",
                payment_id,
                user_id,
                plan
            )

            return payment_id

        except Exception:
            conn.rollback()

            logger.exception(
                "Could not create payment request "
                "for user %s plan %s",
                user_id,
                plan
            )

            return None

        finally:
            conn.close()


def claim_daily_spin(user_id):
    ensure_wallet(user_id)

    today = datetime.now(IST).strftime("%Y-%m-%d")
    now = time.time()

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE, timeout=10)

        try:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT last_spin_date
                FROM wallets
                WHERE user_id = ?
            """, (user_id,)).fetchone()

            if not row:
                conn.rollback()
                return False

            last_spin_date = row[0]

            if last_spin_date == today:
                conn.rollback()
                return False

            conn.execute("""
                UPDATE wallets
                SET spins = spins + 1,
                    last_spin_date = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                today,
                now,
                user_id
            ))

            conn.commit()
            return True

        except Exception:
            conn.rollback()

            logger.exception(
                "Daily spin claim failed for user %s",
                user_id
            )

            return False

        finally:
            conn.close()



def apply_daily_credit(user_id):
    ensure_wallet(user_id)

    today = datetime.now(IST).strftime("%Y-%m-%d")

    # Plan বের করা transaction-এর বাইরে করা হচ্ছে
    # যাতে একই DB lock nested না হয়।
    plan_id, _ = get_user_plan(user_id)

    plan = PLANS.get(plan_id, PLANS["free"])
    daily_amount = int(plan["daily_credits"])

    if daily_amount <= 0:
        return False

    now = time.time()

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE, timeout=10)

        try:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT credits, last_daily_credit_date, daily_streak
                FROM wallets
                WHERE user_id = ?
            """, (user_id,)).fetchone()

            if not row:
                conn.rollback()
                return False

            current_balance, last_date, daily_streak = row

            # আজকের credit আগেই দেওয়া হয়ে থাকলে
            if last_date == today:
                conn.rollback()
                return False

            yesterday = (datetime.now(IST) - timedelta(days=1)).strftime("%Y-%m-%d")
            new_streak = int(daily_streak or 0) + 1 if last_date == yesterday else 1
            new_balance = int(current_balance) + daily_amount

            # Credit + date + streak একই transaction-এর মধ্যে save হবে
            conn.execute("""
                UPDATE wallets
                SET credits = ?,
                    last_daily_credit_date = ?,
                    daily_streak = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                new_balance,
                today,
                new_streak,
                now,
                user_id
            ))

            conn.execute("""
                INSERT INTO credit_transactions
                (
                    user_id,
                    amount,
                    balance_after,
                    tx_type,
                    note,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                daily_amount,
                new_balance,
                "daily_bonus",
                f"{plan_id} daily credit",
                now
            ))

            conn.commit()
            return True

        except Exception:
            conn.rollback()
            logger.exception(
                "Daily credit failed for user %s",
                user_id
            )
            return False

        finally:
            conn.close()


def load_db_state():
    global REQUEST_COUNT

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        cur.execute("SELECT user_id FROM users")
        USER_IDS.update(row[0] for row in cur.fetchall())

        cur.execute("SELECT user_id FROM banned_users")
        BANNED_USERS.update(row[0] for row in cur.fetchall())

        cur.execute("SELECT user_id FROM verified_users")
        VERIFIED_USERS.update(row[0] for row in cur.fetchall())

        cur.execute("""
            SELECT user_id, action, log_time
            FROM logs
            ORDER BY id DESC
            LIMIT 100
        """)

        rows = cur.fetchall()

        for user_id, action, log_time in reversed(rows):
            ACTIVITY_LOGS.append({
                "user_id": user_id,
                "action": action,
                "time": log_time
            })

        cur.execute("""
            SELECT value
            FROM stats
            WHERE key = 'request_count'
        """)

        row = cur.fetchone()

        if row:
            REQUEST_COUNT = row[0]

        conn.close()


def db_add_group(chat_id, title=None):
    """Register a group so admin broadcasts/maintenance notifications can reach it."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT OR IGNORE INTO bot_groups(chat_id, title, first_seen) VALUES(?, ?, ?)",
            (int(chat_id), title, time.time())
        )
        if title is not None:
            conn.execute("UPDATE bot_groups SET title = ? WHERE chat_id = ?", (title, int(chat_id)))
        conn.commit()
        conn.close()

def get_saved_groups():
    """Return registered groups where the bot has been seen/added."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            return conn.execute(
                "SELECT chat_id, title, first_seen FROM bot_groups ORDER BY first_seen DESC"
            ).fetchall()
        finally:
            conn.close()


def db_remove_group(chat_id):
    """Remove a group from the saved group registry."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            conn.execute("DELETE FROM bot_groups WHERE chat_id = ?", (int(chat_id),))
            conn.commit()
        finally:
            conn.close()


def groups_kb():
    rows = get_saved_groups()
    keyboard = []
    for chat_id, title, _ in rows[:30]:
        label = str(title or "Untitled Group")
        if len(label) > 28:
            label = label[:27] + "…"
        keyboard.append([
            InlineKeyboardButton(
                f"👥 {label}",
                callback_data=f"group_info:{chat_id}"
            ),
            InlineKeyboardButton(
                "🗑 REMOVE",
                callback_data=f"group_remove:{chat_id}"
            )
        ])
    keyboard.append([
        InlineKeyboardButton("🔄 REFRESH", callback_data="group_refresh"),
        InlineKeyboardButton("🔙 ADMIN", callback_data="group_admin_back")
    ])
    return InlineKeyboardMarkup(keyboard)


def groups_text():
    rows = get_saved_groups()
    if not rows:
        return (
            "👥 <b>BOT GROUPS</b>\n\n"
            "📭 No groups have been registered yet.\n\n"
            "Add the bot to a group and send /start there."
        )
    lines = [
        "👥 <b>BOT GROUPS</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 Registered groups: <b>{len(rows)}</b>",
        "",
        "Tap a group for details or remove the bot."
    ]
    return "\n".join(lines)


async def group_membership_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track groups where the bot is added, and clean up when removed."""
    cm = update.my_chat_member
    if not cm or not cm.chat or cm.chat.type not in ("group", "supergroup"):
        return

    new_status = getattr(cm.new_chat_member, "status", "")
    if new_status in ("member", "administrator"):
        db_add_group(cm.chat.id, cm.chat.title or "Untitled Group")
        logger.info("Bot added/active in group %s (%s)", cm.chat.id, cm.chat.title)
    elif new_status in ("left", "kicked"):
        db_remove_group(cm.chat.id)
        logger.info("Bot removed from group %s", cm.chat.id)


def get_saved_broadcast_targets():
    """Return saved private users + registered groups, without duplicates."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            users = [int(row[0]) for row in conn.execute("SELECT user_id FROM users").fetchall()]
            groups = [int(row[0]) for row in conn.execute("SELECT chat_id FROM bot_groups").fetchall()]
            return list(dict.fromkeys(users + groups))
        finally:
            conn.close()


def db_add_user(user_id, user=None):
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("INSERT OR IGNORE INTO users(user_id, first_seen) VALUES(?, ?)", (user_id, time.time()))
        if user is not None:
            conn.execute("UPDATE users SET username = ?, first_name = ? WHERE user_id = ?", (getattr(user, "username", None), getattr(user, "first_name", None), user_id))
        conn.commit()
        conn.close()

def get_user_profile(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        row = conn.execute("SELECT user_id, first_seen, username, first_name, referrer_id, referral_count FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
    return row

def set_referrer_once(user_id, referrer_id):
    if user_id == referrer_id or referrer_id <= 0:
        return False
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not row or row[0] is not None or not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (referrer_id,)).fetchone():
                conn.rollback(); return False
            conn.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, user_id))
            conn.execute("INSERT INTO referrals(referrer_id, referred_id, created_at) VALUES (?, ?, ?)", (referrer_id, user_id, time.time()))
            conn.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (referrer_id,))
            conn.commit(); return True
        except Exception:
            conn.rollback(); logger.exception("Failed to set referrer"); return False
        finally: conn.close()

def get_referral_count(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE); row = conn.execute("SELECT referral_count FROM users WHERE user_id = ?", (user_id,)).fetchone(); conn.close()
    return int(row[0]) if row else 0

def reward_referral(user_id, amount=5):
    profile = get_user_profile(user_id)
    if not profile or profile[4] is None: return False
    referrer_id = int(profile[4])
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT referral_rewarded FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if not row or row[0]: conn.rollback(); return False
            conn.execute("UPDATE users SET referral_rewarded = 1 WHERE user_id = ?", (user_id,)); conn.commit()
        except Exception:
            conn.rollback(); logger.exception("Failed to mark referral reward"); return False
        finally: conn.close()
    return add_credits(referrer_id, amount, tx_type="referral_bonus", note=f"Referral bonus for user {user_id}")

def add_protected_entry(value, entry_type, admin_id):
    value = str(value).strip()
    if not value or entry_type not in {"id", "username", "number"}: return False
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            conn.execute("INSERT OR REPLACE INTO protected_entries(value, entry_type, created_at, added_by) VALUES (?, ?, ?, ?)", (value, entry_type, time.time(), admin_id)); conn.commit(); return True
        except Exception:
            conn.rollback(); logger.exception("Failed to add protected entry"); return False
        finally: conn.close()

def remove_protected_entry(value):
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE); cur = conn.execute("DELETE FROM protected_entries WHERE value = ?", (str(value).strip(),)); conn.commit(); conn.close()
    return cur.rowcount > 0

STARTUP_WELCOME_TEXT = (
    "╔════════════════════════════════╗\n"
    "        🚀 <b>SYSTEM ONLINE</b> 🚀\n"
    "╚════════════════════════════════╝\n\n"

    "💎 <b>TRX EDITION PREMIUM</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✨ The bot is now online and fully operational.\n\n"

    "⚡ <b>All Services:</b> ACTIVE\n"
    "🛡️ <b>System Status:</b> STABLE\n"
    "🚀 <b>Performance:</b> OPTIMIZED\n\n"

    "Thank you for being a valued member of\n"
    "<b>TRX EDITION PREMIUM</b>.\n\n"

    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "👑 <b>OWNER</b>   : @INDIANHACKER4\n"
    "📢 <b>CHANNEL</b> : @TRX_EDITION_VIP\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    "💫 <b>Welcome back. Enjoy the premium experience.</b>"
)


def get_saved_user_ids():
    """Return all users who have previously interacted with the bot."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            rows = conn.execute(
                "SELECT user_id FROM users"
            ).fetchall()
            return [int(row[0]) for row in rows]
        finally:
            conn.close()


async def startup_welcome_broadcast(application):
    """Send startup message to all saved users."""

    user_ids = get_saved_user_ids()

    if not user_ids:
        logger.info("Startup welcome: no saved users to notify.")
        return

    sent = 0
    failed = 0

    logger.info(
        "Startup welcome: notifying %d saved users...",
        len(user_ids)
    )

    for user_id in user_ids:
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text=STARTUP_WELCOME_TEXT,
                parse_mode="HTML"
            )

            sent += 1

            # Small delay to avoid hitting Telegram limits
            await asyncio.sleep(0.05)

        except RetryAfter as exc:
            wait_for = float(
                getattr(exc, "retry_after", 1)
            ) + 0.5

            logger.warning(
                "Rate limited. Waiting %.1fs",
                wait_for
            )

            await asyncio.sleep(wait_for)

        except Forbidden:
            failed += 1

            logger.info(
                "User %s blocked the bot or deleted the chat.",
                user_id
            )

        except Exception:
            failed += 1

            logger.warning(
                "Could not send startup welcome to user %s",
                user_id,
                exc_info=True
            )

    logger.info(
        "Startup welcome finished: sent=%d failed=%d total=%d",
        sent,
        failed,
        len(user_ids)
    )

async def api_health_check(application):
    """Lightweight API health probe with latency tracking."""
    started = time.time()
    try:
        response = await asyncio.to_thread(
            requests.get, API_URL, headers=HEADERS, timeout=10
        )
        elapsed = round((time.time() - started) * 1000, 1)
        healthy = response.status_code == 200
        HEALTH_STATE.update({
            "status": "ONLINE" if healthy else "DEGRADED",
            "latency_ms": elapsed,
            "http_status": response.status_code,
            "checked_at": time.time(),
        })
        logger.info("API HEALTH %s | HTTP %s | %sms", HEALTH_STATE["status"], response.status_code, elapsed)
        return healthy
    except Exception as exc:
        elapsed = round((time.time() - started) * 1000, 1)
        HEALTH_STATE.update({
            "status": "OFFLINE",
            "latency_ms": elapsed,
            "http_status": None,
            "checked_at": time.time(),
        })
        logger.warning("API health check failed: %s", exc)
        return False


async def api_health_loop(application):
    while True:
        try:
            await api_health_check(application)
        except Exception:
            logger.exception("API health loop error")
        await asyncio.sleep(10 * 60)


async def post_init(application):
    """Runs automatically when the bot starts."""

    application.create_task(
        startup_welcome_broadcast(application)
    )

    application.create_task(
        expiry_reminder_loop(application)
    )

    application.create_task(
        api_health_loop(application)
    )

    logger.info(
        "All background tasks started."
    )


def db_ban_user(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        conn.execute("""
            INSERT OR REPLACE INTO banned_users(user_id, banned_at)
            VALUES(?, ?)
        """, (user_id, time.time()))

        conn.commit()
        conn.close()


def db_unban_user(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        conn.execute(
            "DELETE FROM banned_users WHERE user_id = ?",
            (user_id,)
        )

        conn.commit()
        conn.close()


def db_verify_user(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        conn.execute("""
            INSERT OR REPLACE INTO verified_users(user_id, verified_at)
            VALUES(?, ?)
        """, (user_id, time.time()))

        conn.commit()
        conn.close()


def db_add_log(user_id, action):
    log_time = time.strftime("%Y-%m-%d %H:%M:%S")

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        conn.execute("""
            INSERT INTO logs(user_id, action, log_time)
            VALUES(?, ?, ?)
        """, (user_id, action, log_time))

        conn.execute("""
            DELETE FROM logs
            WHERE id NOT IN (
                SELECT id
                FROM logs
                ORDER BY id DESC
                LIMIT 100
            )
        """)

        conn.commit()
        conn.close()


def db_increment_requests():
    global REQUEST_COUNT

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE, timeout=10)

        try:
            conn.execute("BEGIN IMMEDIATE")

            conn.execute("""
                UPDATE stats
                SET value = value + 1
                WHERE key = 'request_count'
            """)

            row = conn.execute("""
                SELECT value
                FROM stats
                WHERE key = 'request_count'
            """).fetchone()

            conn.commit()

            if row:
                REQUEST_COUNT = int(row[0])

        except Exception:
            conn.rollback()
            logger.exception(
                "Failed to increment request count"
            )

        finally:
            conn.close()

# ══════════════ API CALLER ══════════════
def call_api(action: str, params: dict):
    """Reliable synchronous API client used from asyncio.to_thread()."""
    request_params = {
        "key": API_KEY_OVERRIDES.get(action, API_KEY),
        "action": action,
        **params
    }
    started = time.time()
    ok = False
    status = "ERROR"
    attempts = 3

    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                API_URL, params=request_params, headers=HEADERS, timeout=30
            )
            if response.status_code in (403, 429):
                if attempt < attempts:
                    time.sleep(1.5 * attempt)
                    continue
                status = f"HTTP {response.status_code}"
                return None

            response.raise_for_status()
            try:
                result = response.json()
            except ValueError:
                status = "INVALID_JSON"
                return None

            ok = True
            status = f"HTTP {response.status_code}"
            return result
        except requests.RequestException as exc:
            status = type(exc).__name__
            logger.warning("API request [%s] attempt %s/%s: %s", action, attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(1.5 * attempt)
            else:
                return None
        except Exception:
            logger.exception("Unexpected API error [%s]", action)
            return None
        finally:
            if attempt == attempts or ok:
                elapsed = round((time.time() - started) * 1000, 1)
                with API_METRICS_LOCK:
                    API_METRICS["total"] += 1
                    API_METRICS["success" if ok else "failed"] += 1
                    API_METRICS["total_ms"] += elapsed
                    API_METRICS["last_ms"] = elapsed
                    API_METRICS["last_status"] = status
                    API_METRICS["last_action"] = str(action)
                    API_METRICS["last_check"] = time.time()

    return None

def fmt(data, indent=0):
    """Pretty-format JSON — SOB VALUE html.escape() hobe (HTML parse fix)"""
    pad = "  " * indent
    out = []
    if isinstance(data, dict):
        for k, v in data.items():
            key = html.escape(str(k).replace("_", " ").title())
            if isinstance(v, (dict, list)):
                out.append(f"{pad}◆ <b>{key}</b>")
                out.append(fmt(v, indent + 1))
            else:
                val = str(v) if v is not None else "N/A"
                val = html.escape(val)          # ← MAIN FIX: & < > escape
                if len(val) > 200:
                    val = val[:200] + "…"
                out.append(f"{pad}• <b>{key}:</b> <code>{val}</code>")
    elif isinstance(data, list):
        for i, item in enumerate(data, 1):
            if isinstance(item, (dict, list)):
                out.append(f"{pad}<b>#{i}</b>")
                out.append(fmt(item, indent + 1))
            else:
                out.append(f"{pad}• <code>{html.escape(str(item))}</code>")
    else:
        out.append(f"{pad}<code>{html.escape(str(data))}</code>")
    return "\n".join(out)

def clean_result(data):
    """
    Remove unwanted credit/footer fields recursively.
    """
    blocked_keys = {"credit", "footer"}

    if isinstance(data, dict):
        return {
            key: clean_result(value)
            for key, value in data.items()
            if str(key).lower() not in blocked_keys
        }

    if isinstance(data, list):
        return [
            clean_result(item)
            for item in data
        ]

    return data

async def safe_send(func, text, **kwargs):
    """Send/edit HTML safely, with plain-text fallback."""
    import re

    kwargs = dict(kwargs)
    kwargs.pop("parse_mode", None)

    try:
        return await func(
            text,
            parse_mode="HTML",
            **kwargs
        )

    except BadRequest:
        plain = re.sub(
            r"</?(?:b|i|code|pre|u|s)>",
            "",
            text
        )

        plain = html.unescape(plain)

        try:
            return await func(
                plain[:4096],
                **kwargs
            )

        except BadRequest:
            try:
                return await func(
                    "⚠️ Result received but could not be displayed.\n"
                    "Use /menu to try again.",
                    **kwargs
                )
            except Exception:
                logger.exception("safe_send fallback failed")
                return None

    except Exception:
        logger.exception("safe_send failed")
        return None

def smart_truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text

    marker = "\n<i>…truncated</i>"

    available = limit - len(marker)

    if available <= 0:
        return marker[:limit]

    cut = text[:available]

    last_nl = cut.rfind("\n")
    if last_nl > 200:
        cut = cut[:last_nl]

    return cut + marker

def is_protected_value(value):
    if not value: return False
    value = str(value).strip()
    if value in PROTECTED_IDS: return True
    username = value.lstrip("@").lower()
    if username in {str(x).lstrip("@").lower() for x in PROTECTED_USERNAMES}: return True
    normalized = re.sub(r"[^\d+]", "", value)
    if normalized in {re.sub(r"[^\d+]", "", str(x)) for x in PROTECTED_NUMBERS}: return True
    try:
        with DB_LOCK:
            conn = sqlite3.connect(DB_FILE); rows = conn.execute("SELECT value, entry_type FROM protected_entries").fetchall(); conn.close()
        for stored, kind in rows:
            stored = str(stored).strip()
            if kind == "id" and value == stored: return True
            if kind == "username" and username == stored.lstrip("@").lower(): return True
            if kind == "number" and normalized == re.sub(r"[^\d+]", "", stored): return True
    except Exception: logger.exception("Protected-entry check failed")
    return False

# ══════════════ STYLES ══════════════
def banner(title="💎 T R X  E D I T I O N"):
    return (
        "╔══════════════════════╗\n"
        f"      {title}\n"
        "          P R E M I U M\n"
        "╚══════════════════════╝\n"
    )



# ═════════════════════════════════════════════════════════════
# 🧰 ADMIN EXTRA SUITE
# Safe admin/analytics utilities. Existing bot functions remain untouched.
# ═════════════════════════════════════════════════════════════

def admin_extra_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ LIVE DASHBOARD", callback_data="extra_dashboard"),
            InlineKeyboardButton("📈 ANALYTICS", callback_data="extra_analytics"),
        ],
        [
            InlineKeyboardButton("🩺 HEALTH CHECK", callback_data="extra_health"),
            InlineKeyboardButton("📊 DAILY REPORT", callback_data="extra_report"),
        ],
        [
            InlineKeyboardButton("🧹 CLEAN LOGS", callback_data="extra_cleanup"),
            InlineKeyboardButton("🔔 ALERT STATUS", callback_data="extra_alerts"),
        ],
        [
            InlineKeyboardButton("🔄 REFRESH", callback_data="extra_refresh"),
            InlineKeyboardButton("🔙 ADMIN", callback_data="extra_admin_back"),
        ],
    ])


def admin_extra_text():
    return (
        "╔══════════════════════════╗\n"
        "      🧰 <b>ADMIN EXTRA SUITE</b>\n"
        "╚══════════════════════════╝\n\n"
        "⚡ Live dashboard & performance\n"
        "📈 Usage analytics & daily activity\n"
        "🩺 API health monitoring\n"
        "📊 CSV report export\n"
        "🧹 Safe log cleanup\n"
        "🔔 Runtime alert status\n\n"
        "👇 Select a tool:"
    )


def _extra_db_stats():
    """Read-only statistics helper; never changes existing bot state."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            groups = conn.execute("SELECT COUNT(*) FROM bot_groups").fetchone()[0]
            try:
                verified = conn.execute("SELECT COUNT(*) FROM verified_users").fetchone()[0]
            except sqlite3.OperationalError:
                verified = 0
            try:
                active_plans = conn.execute(
                    "SELECT COUNT(*) FROM subscriptions WHERE status='active'"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                active_plans = 0
            return users, verified, groups, active_plans
        finally:
            conn.close()


def _extra_activity_stats():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            today_requests = conn.execute(
                "SELECT COUNT(*) FROM logs WHERE log_time LIKE ?",
                (today + "%",)
            ).fetchone()[0]
            top = conn.execute(
                "SELECT action, COUNT(*) FROM logs "
                "WHERE log_time LIKE ? GROUP BY action "
                "ORDER BY COUNT(*) DESC LIMIT 5",
                (today + "%",)
            ).fetchall()
            return today_requests, top
        finally:
            conn.close()


def _extra_cleanup_logs(keep_days=30):
    """Delete only old activity logs. Other tables are never touched."""
    cutoff = time.time() - (keep_days * 86400)
    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)
        try:
            cur = conn.execute(
                "DELETE FROM logs WHERE created_at < ?",
                (cutoff,)
            )
            conn.commit()
            return cur.rowcount
        except sqlite3.OperationalError:
            # Some older schemas may use log_time instead.
            conn.rollback()
            return 0
        finally:
            conn.close()


def _extra_build_report(path):
    users, verified, groups, active_plans = _extra_db_stats()
    today_requests, top = _extra_activity_stats()
    with API_METRICS_LOCK:
        m = dict(API_METRICS)

    total = m.get("total", 0)
    success_rate = (m.get("success", 0) * 100 / total) if total else 0.0

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["TRX EDITION ADMIN REPORT"])
        w.writerow(["Generated", datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")])
        w.writerow([])
        w.writerow(["Metric", "Value"])
        w.writerow(["Users", users])
        w.writerow(["Verified Users", verified])
        w.writerow(["Groups", groups])
        w.writerow(["Active Plans", active_plans])
        w.writerow(["Requests Today", today_requests])
        w.writerow(["Total API Requests", total])
        w.writerow(["API Success", m.get("success", 0)])
        w.writerow(["API Failed", m.get("failed", 0)])
        w.writerow(["API Success Rate", f"{success_rate:.1f}%"])
        w.writerow(["Average API Latency (ms)",
                     f"{(m.get('total_ms', 0)/total):.0f}" if total else "0"])
        w.writerow([])
        w.writerow(["Top Service", "Requests Today"])
        for action, count in top:
            w.writerow([str(action), count])


def admin_kb():
    keyboard = [
        [
            KeyboardButton("📊 STATISTICS", style="primary"),
            KeyboardButton("👥 USERS", style="success"),
        ],
        [
            KeyboardButton("🚫 BAN / UNBAN", style="danger"),
            KeyboardButton("💰 ADD CREDIT", style="success"),
        ],
        [
            KeyboardButton("📢 BROADCAST", style="primary"),
            KeyboardButton("🔧 MAINTENANCE", style="danger"),
        ],
        [
            KeyboardButton("🔎 USER SEARCH", style="primary"),
            KeyboardButton("🛡️ PROTECTION", style="danger"),
        ],
        [
            KeyboardButton("💳 PAYMENTS", style="success"),
        ],
        [
            KeyboardButton("📡 API STATUS", style="success"),
            KeyboardButton("⚡ LIGHTSPEED", style="primary"),
        ],
        [
            KeyboardButton("🧰 MORE TOOLS", style="primary"),
        ],
        [
            KeyboardButton("📋 LOGS", style="primary"),
        ],
        [
            KeyboardButton("👥 GROUPS", style="primary"),
            KeyboardButton("💾 DB BACKUP", style="success"),
        ],
        [
            KeyboardButton("⚙️ SETTINGS", style="success"),
        ],
        [
            KeyboardButton("🔙 ADMIN BACK", style="primary"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✦ TRX ADMIN PANEL ✦"
    )

def main_menu_kb(page=1):
    if page == 1:
        keyboard = [
            [
                KeyboardButton(
                    "🔍  NUMBER SEARCH",
                    style="primary"
                ),
                KeyboardButton(
                    "🆔  AADHAR INFO",
                    style="success"
                ),
            ],

            [
                KeyboardButton(
                    "💎 DASHBOARD",
                    style="primary"
                ),
                KeyboardButton(
                    "📱 TG TO NUMBER",
                    style="success"
                ),
            ],

            [
                KeyboardButton(
                    "👤  TELEGRAM INFO",
                    style="success"
                ),
                KeyboardButton(
                    "📸  INSTAGRAM INFO",
                    style="primary"
                ),
            ],

            [
                KeyboardButton(
                    "🚘  VEHICLE RC  ✦",
                    style="primary"
                ),
            ],

            [
                KeyboardButton(
                    "➡️  NEXT PAGE",
                    style="success"
                ),
            ],
        ]

    elif page == 2:
        keyboard = [
            [
                KeyboardButton(
                    "🌐  IP LOOKUP  ✦",
                    style="success"
                ),
                KeyboardButton(
                    "🌤️  WEATHER  ✦",
                    style="primary"
                ),
            ],

            [
                KeyboardButton(
                    "📱  IMEI INFO",
                    style="primary"
                ),
                KeyboardButton(
                    "📮  PINCODE INFO",
                    style="success"
                ),
            ],

            [
                KeyboardButton(
                    "🏦  IFSC INFO",
                    style="success"
                ),
            ],

            [
                KeyboardButton(
                    "⬅️  PREVIOUS"
                ),
                KeyboardButton(
                    "➡️  NEXT PAGE",
                    style="success"
                ),
            ],
        ]

    else:
        keyboard = [
            [
                KeyboardButton(
                    "🌍  COUNTRY INFO",
                    style="success"
                ),
                KeyboardButton(
                    "💳  UPI INFO",
                    style="primary"
                ),
            ],

            [
                KeyboardButton(
                    "💰  PAYTM INFO",
                    style="danger"
                ),
                KeyboardButton(
                    "📊  BOT STATUS",
                    style="primary"
                ),
            ],

            [
                KeyboardButton("👤  MY PROFILE", style="success"),
                KeyboardButton("🎁  REFERRAL", style="primary"),
            ],
            [
                KeyboardButton(
                    "🆘  PREMIUM HELP",
                    style="danger"
                ),
            ],

            [
                KeyboardButton(
                    "⬅️  PREVIOUS"
                ),
                KeyboardButton(
                    "🏠  MAIN PAGE",
                    style="success"
                ),
            ],
        ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=(
            f"✦ TRX PREMIUM • PAGE {page}/3 ✦"
        )
    )

def vehicle_kb():
    keyboard = [
        [
            KeyboardButton("🚙  VEHICLE V1", style="primary"),
            KeyboardButton("🚕  VEHICLE V2", style="success"),
        ],
        [
            KeyboardButton("🛻  VEHICLE V3", style="success"),
            KeyboardButton("🏎  VEHICLE V4", style="danger"),
        ],
        [
            KeyboardButton("🔙  BACK TO MAIN", style="primary"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✦  TRX VEHICLE • SELECT VERSION  ✦"
    )

def ip_kb():
    keyboard = [
        [
            KeyboardButton("🌐  IP V1", style="primary"),
            KeyboardButton("🌐  IP V2", style="success"),
        ],
        [
            KeyboardButton("🌐  IP V3", style="danger"),
        ],
        [
            KeyboardButton("🔙  BACK TO MAIN", style="primary"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✦  TRX IP • SELECT VERSION  ✦"
    )

def weather_kb():
    keyboard = [
        [
            KeyboardButton("🌤️  WEATHER SEARCH", style="primary"),
            KeyboardButton("🌦️  WEATHER INFO", style="success"),
        ],
        [
            KeyboardButton("🔙  BACK TO MAIN", style="primary"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✦  TRX WEATHER • SELECT SERVICE  ✦"
    )


def plans_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🆓 FREE",
                callback_data="plan:free"
            )
        ],
        [
            InlineKeyboardButton(
                "⭐ VIP",
                callback_data="plan:vip"
            ),
            InlineKeyboardButton(
                "💎 PREMIUM",
                callback_data="plan:premium"
            )
        ],
        [
            InlineKeyboardButton(
                "♾️ LIFETIME",
                callback_data="plan:lifetime"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 BACK",
                callback_data="main_menu"
            )
        ]
    ])


def plans_text():
    free = PLANS["free"]
    vip = PLANS["vip"]
    premium = PLANS["premium"]
    lifetime = PLANS["lifetime"]

    def duration_text(plan):
        days = plan["duration_days"]

        if days is None:
            return "No expiry"

        return f"{days} Days"

    return (
        "╔══════════════════════════╗\n"
        "       ⭐ <b>SUBSCRIPTION PLANS</b>\n"
        "╚══════════════════════════╝\n\n"

        f"🆓 <b>{html.escape(str(free['name']))}</b>\n"
        f"🎟️ Starting Credits: <code>{free['credits']}</code>\n"
        f"🎁 Daily Credits: <code>{free['daily_credits']}</code>\n"
        f"💰 Price: <code>FREE</code>\n"
        "🎰 Free Daily Spin\n\n"

        f"⭐ <b>{html.escape(str(vip['name']))}</b>\n"
        f"📅 Duration: <code>{duration_text(vip)}</code>\n"
        f"🎟️ Credits: <code>{vip['credits']}</code>\n"
        f"🎁 Daily Credits: <code>{vip['daily_credits']}</code>\n"
        f"💰 Price: <code>₹{vip['price']}</code>\n\n"

        f"💎 <b>{html.escape(str(premium['name']))}</b>\n"
        f"📅 Duration: <code>{duration_text(premium)}</code>\n"
        f"🎟️ Credits: <code>{premium['credits']}</code>\n"
        f"🎁 Daily Credits: <code>{premium['daily_credits']}</code>\n"
        f"💰 Price: <code>₹{premium['price']}</code>\n\n"

        f"♾️ <b>{html.escape(str(lifetime['name']))}</b>\n"
        f"🎟️ Credits: <code>{lifetime['credits']}</code>\n"
        f"🎁 Daily Credits: <code>{lifetime['daily_credits']}</code>\n"
        f"💰 Price: <code>₹{lifetime['price']}</code>\n"
        "⏰ No expiry\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 Select a plan below"
    )



def dashboard_kb():
    """Legacy inline dashboard keyboard kept for callback compatibility."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 WALLET", callback_data="dashboard:wallet"),
         InlineKeyboardButton("⭐ PLANS", callback_data="dashboard:plans")],
        [InlineKeyboardButton("🎰 SPIN", callback_data="dashboard:spin"),
         InlineKeyboardButton("📜 HISTORY", callback_data="dashboard:history")],
        [InlineKeyboardButton("🔙 BACK TO MAIN", callback_data="main_menu")],
    ])


def user_dashboard_kb():
    """Bottom reply keyboard for the expanded user dashboard."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💳 WALLET"), KeyboardButton("⭐ PLANS")],
            [KeyboardButton("🎰 SPIN"), KeyboardButton("📜 HISTORY")],
            [KeyboardButton("👤 MY PROFILE"), KeyboardButton("🎁 REFERRAL")],
            [KeyboardButton("📊 MY USAGE"), KeyboardButton("💰 PAYMENT HISTORY")],
            [KeyboardButton("🔔 NOTIFICATIONS"), KeyboardButton("⚙️ SETTINGS")],
            [KeyboardButton("🌐 SERVICE STATUS"), KeyboardButton("❓ HELP & FAQ")],
            [KeyboardButton("📞 SUPPORT"), KeyboardButton("🏠 MAIN PAGE")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✦ TRX USER DASHBOARD ✦"
    )

def dashboard_back_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 BACK TO DASHBOARD",
                callback_data="dashboard:home"
            )
        ],
    ])


def wallet_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⭐ PLANS",
                callback_data="plans"
            ),
            InlineKeyboardButton(
                "🎰 SPIN",
                callback_data="spin"
            )
        ],
        [
            InlineKeyboardButton(
                "📜 HISTORY",
                callback_data="history"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 MAIN MENU",
                callback_data="main_menu"
            )
        ]
    ])


def wallet_text(user_id):
    ensure_wallet(user_id)

    wallet = get_wallet(user_id)
    plan, expires_at = get_user_plan(user_id)

    if expires_at:
        expiry = datetime.fromtimestamp(
            expires_at,
            IST
        ).strftime("%d-%m-%Y %H:%M")
    else:
        expiry = "NO EXPIRY"

    safe_plan = html.escape(
        str(plan).upper()
    )

    return (
        "╔══════════════════════════╗\n"
        "          💳 <b>MY WALLET</b>\n"
        "╚══════════════════════════╝\n\n"

        f"👤 ID: <code>{user_id}</code>\n\n"

        f"📦 Plan: <b>{safe_plan}</b>\n"
        f"💰 Credits: <b>{wallet['credits']}</b>\n"
        f"🎁 Bonus: <b>{wallet['bonus_credits']}</b>\n"
        f"🎰 Spins: <b>{wallet['spins']}</b>\n"
        f"🔥 Daily Streak: <b>{wallet['daily_streak']}</b> days\n"
        f"⏰ Expiry: <b>{html.escape(str(expiry))}</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "💎 <i>TRX EDITION</i>"
    )



def spin_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🎰 SPIN NOW",
                callback_data="spin_now"
            )
        ],
        [
            InlineKeyboardButton(
                "💳 WALLET",
                callback_data="wallet"
            ),
            InlineKeyboardButton(
                "🔙 MAIN",
                callback_data="main_menu"
            )
        ]
    ])

def perform_free_spin(user_id):
    ensure_wallet(user_id)

    roll = secrets.randbelow(100)

    if roll < 60:
        reward_type = "credits"
        reward_value = 2
    elif roll < 85:
        reward_type = "credits"
        reward_value = 5
    elif roll < 95:
        reward_type = "credits"
        reward_value = 10
    else:
        reward_type = "bonus_spin"
        reward_value = 1

    now = time.time()

    with DB_LOCK:
        conn = sqlite3.connect(DB_FILE)

        try:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT credits, spins
                FROM wallets
                WHERE user_id = ?
            """, (user_id,)).fetchone()

            if not row:
                conn.rollback()
                return None

            current_credits, spins = row

            if spins <= 0:
                conn.rollback()
                return None

            new_credits = current_credits

            # প্রথমে ১টা spin খরচ
            conn.execute("""
                UPDATE wallets
                SET spins = spins - 1,
                    updated_at = ?
                WHERE user_id = ?
            """, (now, user_id))

            if reward_type == "credits":
                new_credits = current_credits + reward_value

                conn.execute("""
                    UPDATE wallets
                    SET credits = ?,
                        updated_at = ?
                    WHERE user_id = ?
                """, (
                    new_credits,
                    now,
                    user_id
                ))

                conn.execute("""
                    INSERT INTO credit_transactions
                    (
                        user_id,
                        amount,
                        balance_after,
                        tx_type,
                        note,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    reward_value,
                    new_credits,
                    "spin_reward",
                    "Free spin reward",
                    now
                ))

            elif reward_type == "bonus_spin":
                # ১টা spin খরচ হলেও reward হিসেবে আবার ১টা ফেরত
                conn.execute("""
                    UPDATE wallets
                    SET spins = spins + 1,
                        updated_at = ?
                    WHERE user_id = ?
                """, (now, user_id))

            conn.execute("""
                INSERT INTO spin_history
                (
                    user_id,
                    reward_type,
                    reward_value,
                    created_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                reward_type,
                reward_value,
                now
            ))

            conn.commit()

            return reward_type, reward_value

        except Exception:
            conn.rollback()
            logger.exception("Spin failed")
            return None

        finally:
            conn.close()





def spin_text(user_id):
    ensure_wallet(user_id)

    wallet = get_wallet(user_id)

    return (
        "╔══════════════════════════╗\n"
        "          🎰 <b>DAILY SPIN</b>\n"
        "╚══════════════════════════╝\n\n"

        f"🎰 Available Spins: "
        f"<b>{wallet['spins']}</b>\n\n"

        "🎁 Possible rewards:\n"
        "• 💰 2 Credits\n"
        "• 💰 5 Credits\n"
        "• 💰 10 Credits\n"
        "• 🎰 Bonus Spin\n\n"

        "⚠️ Daily spin is a free bonus feature.\n"
        "It has no cash value.\n\n"

        "👇 Press <b>SPIN NOW</b>"
    )


def transactions_text(user_id):
    ensure_wallet(user_id)

    with DB_LOCK:
        conn = sqlite3.connect(
            DB_FILE,
            timeout=10
        )

        try:
            rows = conn.execute("""
                SELECT
                    amount,
                    balance_after,
                    tx_type,
                    note,
                    created_at
                FROM credit_transactions
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 15
            """, (user_id,)).fetchall()

        except Exception:
            logger.exception(
                "Could not load transaction history for user %s",
                user_id
            )
            return (
                "❌ <b>Could not load credit history.</b>\n\n"
                "Please try again later."
            )

        finally:
            conn.close()

    if not rows:
        return (
            "╔══════════════════════════╗\n"
            "       📜 <b>CREDIT HISTORY</b>\n"
            "╚══════════════════════════╝\n\n"
            "📭 No transactions yet."
        )

    text = (
        "╔══════════════════════════╗\n"
        "       📜 <b>CREDIT HISTORY</b>\n"
        "╚══════════════════════════╝\n\n"
    )

    for amount, balance, tx_type, note, created in rows:

        try:
            date = datetime.fromtimestamp(
                float(created),
                IST
            ).strftime("%d-%m-%Y %H:%M")
        except (TypeError, ValueError, OSError):
            date = "Unknown time"

        try:
            amount_num = float(amount)
        except (TypeError, ValueError):
            amount_num = 0

        if amount_num > 0:
            sign = "+"
        else:
            sign = ""

        safe_type = html.escape(
            str(tx_type)
        )

        safe_amount = html.escape(
            f"{amount_num:g}"
        )

        safe_balance = html.escape(
            str(balance)
        )

        text += (
            f"ð <code>{date}</code>\n"
            f"⚡ <b>{safe_type}</b>\n"
            f"💰 Amount: <b>{sign}{safe_amount}</b>\n"
            f"💳 Balance: <b>{safe_balance}</b>\n"
        )

        if note:
            text += (
                f"📝 {html.escape(str(note))}\n"
            )

        text += "\n"

    return smart_truncate(
        text,
        limit=4000
    )


def back_kb():
    keyboard = [
        [
            KeyboardButton("🔙  BACK TO MAIN", style="primary"),
        ]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✦  TRX PREMIUM • BACK TO MAIN  ✦"
    )

# ══════════════ ACTION REGISTRY ══════════════
ACTIONS = {
    "num":         ("num",            "number",    "🔍 NUMBER SEARCH\n\nSend phone number:\n<i>Ex:</i> <code>9876543210</code>", lambda x: x.strip()),
    "aadhar":      ("aadhar",         "aadhar",    "🆔 AADHAR INFO\n\nSend Aadhar number:\n<i>Ex:</i> <code>327567544017</code>", lambda x: x.strip()),
    "tg":          ("tg-registration","userid",    "👤 TELEGRAM INFO\n\nSend Telegram User ID:\n<i>Ex:</i> <code>1234567890</code>", lambda x: x.strip()),
    "insta":       ("instagram-user", "username",  "📸 INSTAGRAM INFO\n\nSend username:\n<i>Ex:</i> <code>mahajann_24</code>", lambda x: x.strip().lstrip("@")),
    "imei":        ("imei-info",      "imei_num",  "📱 IMEI INFO\n\nSend IMEI number:\n<i>Ex:</i> <code>353010111111110</code>", lambda x: x.strip()),
    "pin":         ("pincode-info",   "pincode",   "📮 PINCODE INFO\n\nSend pincode:\n<i>Ex:</i> <code>110001</code>", lambda x: x.strip()),
    "ifsc":        ("ifsc-info",      "ifsc",      "🏦 IFSC INFO\n\nSend IFSC code:\n<i>Ex:</i> <code>SBIN0000001</code>", lambda x: x.strip().upper()),
    "country":     ("country-info",   "name",      "🌍 COUNTRY INFO\n\nSend country name:\n<i>Ex:</i> <code>india</code>", lambda x: x.strip().lower()),
    "upi":         ("upiinfo",        "upi",       "💳 UPI INFO\n\nSend UPI ID:\n<i>Ex:</i> <code>example@ybl</code>", lambda x: x.strip()),
    "paytm":       ("paytm",          "info",      "💰 PAYTM INFO\n\nSend number:\n<i>Ex:</i> <code>9876543210</code>", lambda x: x.strip()),
    "v1":          ("vehicle-v1",     "rc",        "🚙 VEHICLE V1\n\nSend RC number:\n<i>Ex:</i> <code>MH12DE1433</code>", lambda x: x.strip().upper().replace(" ", "")),
    "v2":          ("vehicle-v2",     "rc",        "🚕 VEHICLE V2\n\nSend RC number:\n<i>Ex:</i> <code>MH12DE1433</code>", lambda x: x.strip().upper().replace(" ", "")),
    "v3":          ("vehicle-v3",     "rc",        "🛻 VEHICLE V3\n\nSend RC number:\n<i>Ex:</i> <code>MH12DE1433</code>", lambda x: x.strip().upper().replace(" ", "")),
    "v4":          ("vehicle-v4",     "rc",        "🏎 VEHICLE V4\n\nSend RC number:\n<i>Ex:</i> <code>MH12DE1433</code>", lambda x: x.strip().upper().replace(" ", "")),
    "ipv1":        ("ip-v1",          "query",     "🌐 IP V1\n\nSend IP:\n<i>Ex:</i> <code>8.8.8.8</code>", lambda x: x.strip()),
    "ipv2":        ("ip-v2",          "ip",        "🌐 IP V2\n\nSend IP:\n<i>Ex:</i> <code>157.35.26.44</code>", lambda x: x.strip()),
    "ipv3":        ("ip-v3",          "ip",        "🌐 IP V3\n\nSend IP:\n<i>Ex:</i> <code>157.35.26.44</code>", lambda x: x.strip()),
    "weather":     ("weather",        "search",    "🌦 WEATHER SEARCH\n\nSend city:\n<i>Ex:</i> <code>Delhi</code>", lambda x: x.strip().title()),
    "weatherinfo": ("weather-info",   "city",      "🌦 WEATHER INFO\n\nSend city:\n<i>Ex:</i> <code>Delhi</code>", lambda x: x.strip().title()),
    "tgid_num": ("tgid", "id", "📱 TG TO NUMBER\n\nSend Telegram User ID:\n<i>Ex:</i> <code>8771611214</code>", lambda x: x.strip()),
}

# ══════════════ CHANNEL JOIN VERIFY ══════════════
async def is_member(bot, user_id) -> bool:
    try:
        m = await bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id
        )

        if m.status in ("member", "administrator", "creator"):
            VERIFIED_USERS.add(user_id)
            db_verify_user(user_id)
            return True

    except Exception as e:
        logger.error(f"Join check error: {e}")

    return False

def join_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Join Channel",
                url=CHANNEL_LINK,
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Check Join",
                callback_data="check_join",
                style="success"
            )
        ]
    ])

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user: return
    user = update.effective_user; user_id = user.id
    USER_IDS.add(user_id); db_add_user(user_id, user); ensure_wallet(user_id); claim_daily_spin(user_id); apply_daily_credit(user_id)
    profile = get_user_profile(user_id); wallet = get_wallet(user_id); plan, expires = get_user_plan(user_id)
    username = f"@{user.username}" if user.username else "Not set"
    bot_username = context.bot.username or "your_bot"; link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    expiry = datetime.fromtimestamp(expires, IST).strftime("%d-%m-%Y %H:%M") if expires else "NO EXPIRY"
    await update.message.reply_text(
        "╔══════════════════════════╗\n👤 <b>MY PROFILE</b>\n╚══════════════════════════╝\n\n"
        f"👤 Name: <b>{html.escape(str(user.first_name or 'User'))}</b>\n"
        f"🔹 Username: <b>{html.escape(username)}</b>\n"
        f"🆔 User ID: <code>{user_id}</code>\n\n"
        f"💎 Plan: <b>{html.escape(str(plan).upper())}</b>\n"
        f"💰 Credits: <b>{wallet['credits']}</b>\n"
        f"🎁 Bonus: <b>{wallet['bonus_credits']}</b>\n"
        f"👥 Referrals: <b>{get_referral_count(user_id)}</b>\n"
        f"🔥 Daily Streak: <b>{wallet['daily_streak']}</b> days\n"
        f"⏰ Expiry: <b>{expiry}</b>\n\n"
        f"🔗 Referral link:\n<code>{html.escape(link)}</code>",
        parse_mode="HTML", reply_markup=back_kb())

async def referral_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user: return
    user_id=update.effective_user.id; db_add_user(user_id, update.effective_user)
    bot_username=context.bot.username or "your_bot"; link=f"https://t.me/{bot_username}?start=ref_{user_id}"
    await update.message.reply_text(
        "🎁 <b>REFERRAL PROGRAM</b>\n\n"
        f"👥 Successful referrals: <b>{get_referral_count(user_id)}</b>\n"
        "💰 Reward: <b>5 credits</b> per eligible referral\n\n"
        f"🔗 <code>{html.escape(link)}</code>", parse_mode="HTML", reply_markup=back_kb())

# ══════════════ HANDLERS ══════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if update.effective_chat and update.effective_chat.type in ("group", "supergroup"):
        db_add_group(update.effective_chat.id, update.effective_chat.title)

    USER_IDS.add(user_id)
    db_add_user(user_id, user)

    if context.args:
        payload = str(context.args[0]).strip()
        if payload.startswith("ref_"):
            try:
                referrer_id = int(payload[4:])
                if set_referrer_once(user_id, referrer_id):
                    reward_referral(user_id, 5)
                    add_log(user_id, f"Joined via referral {referrer_id}")
            except ValueError:
                pass

    # =========================
    # BAN CHECK
    # =========================
    if user_id in BANNED_USERS and not is_admin(user_id):
        await update.message.reply_text(
            "🚫 <b>You are banned from using this bot.</b>\n\n"
            "You cannot access the bot services.",
            parse_mode="HTML"
        )
        return

    # =========================
    # MAINTENANCE CHECK
    # =========================
    if MAINTENANCE_MODE and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ <b>BOT UNDER MAINTENANCE</b>\n\n"
            "Please try again later.",
            parse_mode="HTML"
        )
        return

    # =========================
    # WALLET / DAILY REWARDS
    # Only allowed users reach here
    # =========================
    

    # Clear old temporary input state
    context.user_data.clear()

    text = (
        banner() + "\n"
        "🌈 ✦ PREMIUM ACCESS ✦ 🌈\n\n"
        "📢 Join our official channel first.\n"
        "✅ Then verify your membership.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👇 GET STARTED BELOW\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    if update.message:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=join_kb()
        )

    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=join_kb()
        )


async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    # =========================
    # BAN CHECK
    # =========================
    if user_id in BANNED_USERS and not is_admin(user_id):
        await query.answer(
            "🚫 You are banned.",
            show_alert=True
        )
        return

    # =========================
    # MAINTENANCE CHECK
    # =========================
    if MAINTENANCE_MODE and not is_admin(user_id):
        await query.answer(
            "🛠️ Bot is under maintenance.",
            show_alert=True
        )
        return

    # =========================
    # ADMIN BYPASS
    # =========================
    if is_admin(user_id):
        await query.answer("✅ Admin access granted!")
        await show_main(query)
        return

    # =========================
    # CHANNEL VERIFICATION
    # =========================
    if await is_member(context.bot, user_id):

        VERIFIED_USERS.add(user_id)
        db_verify_user(user_id)

        # Give daily rewards only after valid access
        ensure_wallet(user_id)
        claim_daily_spin(user_id)
        apply_daily_credit(user_id)

        await query.answer("✅ Verified!")

        await show_main(query)

    else:
        await query.answer(
            "❌ First join the channel!",
            show_alert=True
        )


async def show_main(query):
    uptime = int(time.time() - START_TIME)

    text = (
        "╔════════════════════════════╗\n"
        "       💎 <b>TRX EDITION</b> 💎\n"
        "        <i>PREMIUM PANEL</i>\n"
        "╚════════════════════════════╝\n\n"

        "🌈 <b>✦ PREMIUM ACCESS ACTIVATED ✦</b> 🌈\n\n"

        "⚡ <b>FAST SERVICE</b>\n"
        "💎 <b>PREMIUM EXPERIENCE</b>\n"
        "🛡️ <b>VERIFIED ACCESS</b>\n"
        f"⏱ <b>UPTIME:</b> "
        f"<code>{uptime//3600}h {(uptime%3600)//60}m</code>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "       👑 <b>VIP CONTROL PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🔐 <b>SECURE SERVICE ACCESS</b>\n"
        "⚡ <b>FAST RESPONSE SYSTEM</b>\n"
        "💎 <b>PREMIUM USER EXPERIENCE</b>\n\n"

        "👇 <b>SELECT YOUR SERVICE BELOW</b>"
    )

    await safe_send(
        query.edit_message_text,
        text,
        parse_mode="HTML"
    )

    # Keep your existing second menu message
    if query.message:
        await query.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "   💎 <b>TRX PREMIUM PANEL</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            "✨ <b>Welcome to VIP Control Center</b>\n"
            "👇 Select your service:",
            parse_mode="HTML",
            reply_markup=main_menu_kb(1)
        )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    # =========================
    # BAN CHECK
    # =========================
    if user_id in BANNED_USERS and not is_admin(user_id):
        await query.answer(
            "🚫 You are banned.",
            show_alert=True
        )
        return

    # =========================
    # MAINTENANCE CHECK
    # =========================
    if MAINTENANCE_MODE and not is_admin(user_id):
        await query.answer(
            "🛠️ Bot is under maintenance.",
            show_alert=True
        )
        return

    # =========================
    # ADMIN BYPASS
    # =========================
    if not is_admin(user_id):

        if not await is_member(context.bot, user_id):
            await query.answer(
                "❌ Join channel first!",
                show_alert=True
            )
            return

    await query.answer()

    await show_main(query)


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    USER_IDS.add(user_id)
    db_add_user(user_id)

    # =========================
    # BAN CHECK
    # =========================
    if user_id in BANNED_USERS and not is_admin(user_id):
        await update.message.reply_text(
            "🚫 <b>You are banned from using this bot.</b>",
            parse_mode="HTML"
        )
        return

    # =========================
    # MAINTENANCE CHECK
    # =========================
    if MAINTENANCE_MODE and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ <b>BOT UNDER MAINTENANCE</b>\n\n"
            "Please try again later.",
            parse_mode="HTML"
        )
        return

    # =========================
    # CHANNEL CHECK
    # Admin does NOT need to join
    # =========================
    if not is_admin(user_id):

        if not await is_member(context.bot, user_id):
            await update.message.reply_text(
                "❌ <b>Channel join koro first!</b>\n\n"
                "Join the official channel and try again.",
                parse_mode="HTML",
                reply_markup=join_kb()
            )
            return

    # =========================
    # WALLET / DAILY REWARDS
    # =========================
    ensure_wallet(user_id)
    claim_daily_spin(user_id)
    apply_daily_credit(user_id)

    uptime = int(time.time() - START_TIME)

    text = (
        "╔════════════════════════════╗\n"
        "       💎 <b>TRX EDITION</b> 💎\n"
        "        <i>PREMIUM PANEL</i>\n"
        "╚════════════════════════════╝\n\n"

        "👑 <b>VIP CONTROL CENTER</b>\n\n"

        "⚡ Fast Service\n"
        "💎 Premium Experience\n"
        "🛡️ Verified Access\n"

        f"⏱ Uptime: <code>"
        f"{uptime//3600}h "
        f"{(uptime%3600)//60}m</code>\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 <b>SELECT YOUR SERVICE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_kb(1)
    )

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_IDS.add(user_id)
    db_add_user(user_id)

    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ <b>ACCESS DENIED</b>\n\n"
            "You are not authorized to use the Admin Panel.",
            parse_mode="HTML"
        )
        return

    context.user_data.pop("admin_mode", None)

    await update.message.reply_text(
        "╔══════════════════════════╗\n"
        "        👑 <b>ADMIN PANEL</b>\n"
        "╚══════════════════════════╝\n\n"
        "📊 Statistics\n"
        "👥 User Management\n"
        "🚫 Ban / Unban\n"
        "📢 Broadcast\n"
        "🔧 Maintenance\n"
        "📡 API Status\n"
        "📋 Activity Logs\n"
        "⚙️ Settings\n\n"
        "👇 Select an option:",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )


async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    user_id = query.from_user.id
    data = query.data or ""

    # =========================================================
    # USER REGISTER
    # =========================================================
    USER_IDS.add(user_id)
    db_add_user(user_id)

    # =========================================================
    # BAN CHECK
    # =========================================================
    if user_id in BANNED_USERS and not is_admin(user_id):

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        await query.answer(
            "🚫 You are banned.",
            show_alert=True
        )
        return

    # =========================================================
    # MAINTENANCE CHECK
    # =========================================================
    if MAINTENANCE_MODE and not is_admin(user_id):

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        await query.answer(
            "🛠️ Bot is under maintenance.",
            show_alert=True
        )
        return

    # =========================================================
    # ADMIN CALLBACK SECURITY
    # =========================================================
    if (data.startswith("admin_") or data.startswith("group_") or data.startswith("extra_")) and not is_admin(user_id):

        await query.answer(
            "⛔ Admin access required.",
            show_alert=True
        )
        return

    # =========================================================
    # ADMIN EXTRA SUITE CALLBACKS
    # =========================================================
    if data in ("extra_refresh", "extra_admin_back"):
        await query.answer("🔄 Refreshed" if data == "extra_refresh" else "")
        if data == "extra_admin_back":
            await query.edit_message_text(
                "👑 <b>ADMIN PANEL</b>\n\n👇 Use the admin keyboard below.",
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text(
                admin_extra_text(),
                parse_mode="HTML",
                reply_markup=admin_extra_kb()
            )
        return

    if data == "extra_dashboard":
        users, verified, groups, active_plans = _extra_db_stats()
        today_requests, _ = _extra_activity_stats()
        with API_METRICS_LOCK:
            m = dict(API_METRICS)
        total = m.get("total", 0)
        rate = (m.get("success", 0) * 100 / total) if total else 0.0
        uptime = max(0, int(time.time() - START_TIME))
        await query.answer()
        await query.edit_message_text(
            "⚡ <b>LIVE ADMIN DASHBOARD</b>\n\n"
            f"👤 Users: <code>{users}</code>\n"
            f"🟢 Active today: <code>{today_requests}</code>\n"
            f"✅ Verified: <code>{verified}</code>\n"
            f"💎 Active plans: <code>{active_plans}</code>\n"
            f"👥 Groups: <code>{groups}</code>\n\n"
            f"📡 API success rate: <code>{rate:.1f}%</code>\n"
            f"⚡ Avg latency: <code>{((m.get('total_ms', 0) / total) if total else 0):.0f} ms</code>",
            parse_mode="HTML",
            reply_markup=admin_extra_kb()
        )
        return

    if data == "extra_analytics":
        today_requests, top = _extra_activity_stats()
        lines = [
            "📈 <b>TODAY'S ANALYTICS</b>",
            "",
            f"📊 Requests today: <code>{today_requests}</code>",
            "",
            "🏆 <b>TOP SERVICES</b>"
        ]
        if top:
            lines.extend(
                f"{i}. {html.escape(str(action))} — <b>{count}</b>"
                for i, (action, count) in enumerate(top, 1)
            )
        else:
            lines.append("📭 No activity yet.")
        await query.answer()
        await query.edit_message_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=admin_extra_kb()
        )
        return

    if data == "extra_health":
        with API_METRICS_LOCK:
            m = dict(API_METRICS)
        health = dict(HEALTH_STATE)
        age = int(time.time() - health["checked_at"]) if health.get("checked_at") else None
        await query.answer()
        await query.edit_message_text(
            "🩺 <b>SYSTEM HEALTH</b>\n\n"
            f"🤖 Bot: <b>ONLINE</b>\n"
            f"📡 API: <b>{html.escape(str(health.get('status','UNKNOWN')))}</b>\n"
            f"⚡ Last latency: <code>{health.get('latency_ms') or 0:.0f} ms</code>\n"
            f"🕐 Health checked: <code>{age if age is not None else '-'}s ago</code>\n"
            f"📊 API calls tracked: <code>{m.get('total',0)}</code>\n"
            f"❌ API failures: <code>{m.get('failed',0)}</code>",
            parse_mode="HTML", reply_markup=admin_extra_kb()
        )
        return

    if data == "extra_report":
        path = None
        try:
            fd, path = tempfile.mkstemp(prefix="trx_report_", suffix=".csv")
            os.close(fd)
            _extra_build_report(path)
            await query.answer("📊 Report ready")
            with open(path, "rb") as report_file:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=report_file,
                    caption="📊 TRX EDITION daily admin report"
                )
        except Exception:
            logger.exception("Failed to create admin report")
            await query.answer("❌ Report failed", show_alert=True)
        finally:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass
        return

    if data == "extra_cleanup":
        try:
            removed = _extra_cleanup_logs(30)
            await query.answer(f"🧹 Removed {removed} old logs")
            await query.edit_message_text(
                f"🧹 <b>LOG CLEANUP COMPLETE</b>\n\n"
                f"Removed old logs: <code>{removed}</code>\n"
                f"Kept the last <b>30 days</b> of logs.",
                parse_mode="HTML", reply_markup=admin_extra_kb()
            )
        except Exception:
            logger.exception("Log cleanup failed")
            await query.answer("❌ Cleanup failed", show_alert=True)
        return

    if data == "extra_alerts":
        await query.answer()
        await query.edit_message_text(
            "🔔 <b>ALERT STATUS</b>\n\n"
            "🩺 API health monitoring: <b>ACTIVE</b>\n"
            "📋 Activity logging: <b>ACTIVE</b>\n"
            "💾 Database backup: <b>AVAILABLE</b>\n"
            "🛡️ Admin callback protection: <b>ACTIVE</b>\n\n"
            "ℹ️ Alerts use the bot's existing runtime monitoring.",
            parse_mode="HTML", reply_markup=admin_extra_kb()
        )
        return

    # =========================================================
    # GROUP MANAGEMENT
    # =========================================================
    if data == "group_refresh":
        await query.answer("🔄 Refreshed")
        await query.edit_message_text(
            groups_text(),
            parse_mode="HTML",
            reply_markup=groups_kb()
        )
        return

    if data == "group_admin_back":
        await query.answer()
        await query.edit_message_text(
            "👑 <b>ADMIN PANEL</b>\n\n👇 Use the admin keyboard below.",
            parse_mode="HTML"
        )
        return

    if data.startswith("group_info:"):
        try:
            chat_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await query.answer("❌ Invalid group.", show_alert=True)
            return
        rows = [r for r in get_saved_groups() if int(r[0]) == chat_id]
        if not rows:
            await query.answer("❌ Group is no longer registered.", show_alert=True)
            return
        _, title, first_seen = rows[0]
        added = datetime.fromtimestamp(float(first_seen), IST).strftime("%d-%m-%Y %H:%M")
        try:
            chat = await context.bot.get_chat(chat_id)
            current_title = chat.title or title or "Untitled Group"
        except Exception:
            current_title = title or "Untitled Group"
        await query.answer()
        await query.edit_message_text(
            "👥 <b>GROUP DETAILS</b>\n\n"
            f"🏷 Name: <b>{html.escape(str(current_title))}</b>\n"
            f"🆔 Chat ID: <code>{chat_id}</code>\n"
            f"📅 First seen: <code>{added}</code>\n\n"
            "🟢 The bot is registered in this group.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 REMOVE BOT", callback_data=f"group_remove:{chat_id}")],
                [InlineKeyboardButton("🔙 GROUP LIST", callback_data="group_refresh")]
            ])
        )
        return

    if data.startswith("group_remove:"):
        try:
            chat_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await query.answer("❌ Invalid group.", show_alert=True)
            return

        rows = [r for r in get_saved_groups() if int(r[0]) == chat_id]
        if not rows:
            await query.answer("❌ Group not found.", show_alert=True)
            return

        try:
            await context.bot.leave_chat(chat_id)
            db_remove_group(chat_id)
            await query.answer("✅ Bot removed from the group.", show_alert=True)
        except Forbidden:
            db_remove_group(chat_id)
            await query.answer("✅ Bot is no longer in that group.", show_alert=True)
        except BadRequest as exc:
            await query.answer(f"❌ Could not remove bot: {exc}", show_alert=True)
        except Exception:
            logger.exception("Failed to leave group %s", chat_id)
            await query.answer("❌ Failed to remove bot from this group.", show_alert=True)

        await query.edit_message_text(
            groups_text(),
            parse_mode="HTML",
            reply_markup=groups_kb()
        )
        return

    # =========================================================
    # CHANNEL JOIN CHECK
    # =========================================================
    if not is_admin(user_id):

        try:
            member = await is_member(
                context.bot,
                user_id
            )

        except Exception:

            logger.exception(
                "Channel membership check failed for user %s",
                user_id
            )

            await query.answer(
                "⚠️ Could not verify channel membership.",
                show_alert=True
            )
            return

        if not member:

            context.user_data.pop("mode", None)
            context.user_data.pop("admin_mode", None)

            await query.answer(
                "❌ Join channel first!",
                show_alert=True
            )
            return

    # =========================================================
    # ANSWER CALLBACK
    # =========================================================
    try:
        await query.answer()
    except BadRequest:
        pass

    # =========================================================
    # =========================================================
    # YOUR DASHBOARD
    # =========================================================
    # =========================================================
    if data.startswith("dashboard:"):

        dashboard_action = data.split(
            ":",
            1
        )[1].strip()

        # =====================================================
        # DASHBOARD HOME
        # =====================================================
        if dashboard_action == "home":

            context.user_data.pop("mode", None)
            context.user_data.pop("admin_mode", None)

            ensure_wallet(user_id)

            claim_daily_spin(user_id)
            apply_daily_credit(user_id)

            dashboard_text = (
                "╔══════════════════════════╗\n"
                "       💎 <b>YOUR DASHBOARD</b>\n"
                "╚══════════════════════════╝\n\n"

                f"👤 User ID: <code>{user_id}</code>\n\n"

                "💳 <b>WALLET</b>\n"
                "Check credits, bonus & expiry\n\n"

                "⭐ <b>PLANS</b>\n"
                "View available subscription plans\n\n"

                "🎰 <b>SPIN</b>\n"
                "Use your available free spin\n\n"

                "📜 <b>HISTORY</b>\n"
                "View your credit transactions\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n"
                "👇 <b>Select an option below</b>"
            )

            await safe_send(
                query.edit_message_text,
                dashboard_text,
                parse_mode="HTML",
                reply_markup=dashboard_kb()
            )

            return

        # =====================================================
        # DASHBOARD WALLET
        # =====================================================
        if dashboard_action == "wallet":

            context.user_data.pop("mode", None)
            context.user_data.pop("admin_mode", None)

            ensure_wallet(user_id)

            claim_daily_spin(user_id)
            apply_daily_credit(user_id)

            wallet_dashboard_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⭐ PLANS",
                        callback_data="dashboard:plans"
                    ),
                    InlineKeyboardButton(
                        "🎰 SPIN",
                        callback_data="dashboard:spin"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📜 HISTORY",
                        callback_data="dashboard:history"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔙 BACK TO DASHBOARD",
                        callback_data="dashboard:home"
                    ),
                ],
            ])

            await safe_send(
                query.edit_message_text,
                wallet_text(user_id),
                parse_mode="HTML",
                reply_markup=wallet_dashboard_kb
            )

            return

        # =====================================================
        # DASHBOARD PLANS
        # =====================================================
        if dashboard_action == "plans":

            context.user_data.pop("mode", None)
            context.user_data.pop("admin_mode", None)

            plans_dashboard_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 BACK TO DASHBOARD",
                        callback_data="dashboard:home"
                    ),
                ],
            ])

            await safe_send(
                query.edit_message_text,
                plans_text(),
                parse_mode="HTML",
                reply_markup=plans_dashboard_kb
            )

            return

        # =====================================================
        # DASHBOARD SPIN
        # =====================================================
        if dashboard_action == "spin":

            context.user_data.pop("mode", None)
            context.user_data.pop("admin_mode", None)

            ensure_wallet(user_id)

            claim_daily_spin(user_id)

            spin_dashboard_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🎰 SPIN NOW",
                        callback_data="spin_now"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔙 BACK TO DASHBOARD",
                        callback_data="dashboard:home"
                    ),
                ],
            ])

            await safe_send(
                query.edit_message_text,
                spin_text(user_id),
                parse_mode="HTML",
                reply_markup=spin_dashboard_kb
            )

            return

        # =====================================================
        # DASHBOARD HISTORY
        # =====================================================
        if dashboard_action == "history":

            context.user_data.pop("mode", None)
            context.user_data.pop("admin_mode", None)

            try:

                history_text = transactions_text(
                    user_id
                )

            except Exception:

                logger.exception(
                    "History error for user %s",
                    user_id
                )

                history_text = (
                    "❌ <b>HISTORY ERROR</b>\n\n"
                    "Unable to load your transaction "
                    "history right now."
                )

            history_dashboard_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "💳 WALLET",
                        callback_data="dashboard:wallet"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔙 BACK TO DASHBOARD",
                        callback_data="dashboard:home"
                    ),
                ],
            ])

            await safe_send(
                query.edit_message_text,
                history_text,
                parse_mode="HTML",
                reply_markup=history_dashboard_kb
            )

            return

        # =====================================================
        # INVALID DASHBOARD ACTION
        # =====================================================
        await safe_send(
            query.edit_message_text,
            "❌ <b>Invalid dashboard option.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "💎 DASHBOARD",
                        callback_data="dashboard:home"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔙 MAIN MENU",
                        callback_data="main_menu"
                    ),
                ],
            ])
        )

        return

    # =========================================================
    # PLAN DETAILS
    # =========================================================
    if data.startswith("plan:"):

        plan_id = data.split(
            ":",
            1
        )[1].strip()

        if plan_id not in PLANS:

            await safe_send(
                query.edit_message_text,
                "❌ <b>Invalid plan.</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔙 BACK TO PLANS",
                            callback_data="dashboard:plans"
                        )
                    ]
                ])
            )

            return

        plan = PLANS[plan_id]

        duration = plan["duration_days"]

        if duration is None:
            duration_text = "Lifetime"
        else:
            duration_text = f"{duration} Days"

        text = (
            "╔══════════════════════════╗\n"
            f"       {html.escape(str(plan['name']))}\n"
            "╚══════════════════════════╝\n\n"

            f"🎟️ Starting Credits: "
            f"<b>{plan['credits']}</b>\n"

            f"🎁 Daily Credits: "
            f"<b>{plan['daily_credits']}</b>\n"

            f"📅 Duration: "
            f"<b>{html.escape(str(duration_text))}</b>\n\n"

            f"💰 Price: "
            f"<b>₹{plan['price']}</b>\n\n"

            "⚠️ Payment/activation will be handled "
            "through the configured admin approval flow."
        )

        await safe_send(
            query.edit_message_text,
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "💳 REQUEST PLAN",
                        callback_data=f"buy:{plan_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 BACK TO PLANS",
                        callback_data="dashboard:plans"
                    )
                ]
            ])
        )

        return

    # =========================================================
    # BUY PLAN
    # =========================================================
    if data.startswith("buy:"):

        plan_id = data.split(
            ":",
            1
        )[1].strip()

        if plan_id not in PLANS:

            await safe_send(
                query.edit_message_text,
                "❌ <b>Invalid plan.</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔙 BACK TO PLANS",
                            callback_data="dashboard:plans"
                        )
                    ]
                ])
            )

            return

        plan = PLANS[plan_id]

        # =====================================================
        # FREE PLAN
        # =====================================================
        if plan_id == "free":

            current_plan, _ = get_user_plan(
                user_id
            )

            # -------------------------------------------------
            # PAID PLAN ACTIVE
            # -------------------------------------------------
            if current_plan != "free":

                await safe_send(
                    query.edit_message_text,
                    "⚠️ <b>FREE PLAN CANNOT BE ACTIVATED</b>\n\n"
                    "তোমার বর্তমানে একটি paid plan active আছে।\n\n"
                    "⏳ Paid plan শেষ হওয়ার পরে FREE plan "
                    "ব্যবহার করতে পারবে।",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "📊 MY PLAN",
                                callback_data="q:status"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🔙 BACK TO PLANS",
                                callback_data="dashboard:plans"
                            )
                        ]
                    ])
                )

                return

            # -------------------------------------------------
            # ACTIVATE FREE
            # -------------------------------------------------
            success = activate_plan(
                user_id,
                "free",
                payment_ref=f"FREE-{user_id}"
            )

            if not success:

                await safe_send(
                    query.edit_message_text,
                    "❌ <b>FREE PLAN ACTIVATION FAILED</b>\n\n"
                    "সম্ভবত FREE plan আগে থেকেই activate করা হয়েছে।\n\n"
                    "💳 Wallet থেকে তোমার current balance দেখো।",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "💳 WALLET",
                                callback_data="dashboard:wallet"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🔙 BACK TO PLANS",
                                callback_data="dashboard:plans"
                            )
                        ]
                    ])
                )

                return

            # -------------------------------------------------
            # SUCCESS
            # -------------------------------------------------
            await safe_send(
                query.edit_message_text,
                "╔══════════════════════════╗\n"
                "       🆓 <b>FREE PLAN</b>\n"
                "╚══════════════════════════╝\n\n"
                "✅ Free plan activated successfully!\n\n"
                f"🎟️ Starting Credits: "
                f"<b>{plan['credits']}</b>\n"
                f"🎁 Daily Credits: "
                f"<b>{plan['daily_credits']}</b>\n\n"
                "💳 Open Wallet to see your balance.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "💳 WALLET",
                            callback_data="dashboard:wallet"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 BACK TO PLANS",
                            callback_data="dashboard:plans"
                        )
                    ]
                ])
            )

            return

        # =====================================================
        # PAID PLAN
        # =====================================================
        payment_id = create_payment_request(
            user_id,
            plan_id,
            plan["price"]
        )

        if payment_id is None:

            await safe_send(
                query.edit_message_text,
                "❌ <b>Could not create payment request.</b>\n\n"
                "Please try again later.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔙 BACK TO PLANS",
                            callback_data="dashboard:plans"
                        )
                    ]
                ])
            )

            return

        await safe_send(
            query.edit_message_text,
            "╔══════════════════════════╗\n"
            "       💳 <b>PLAN REQUEST</b>\n"
            "╚══════════════════════════╝\n\n"
            f"⭐ Plan: "
            f"<b>{html.escape(str(plan['name']))}</b>\n"
            f"💰 Amount: "
            f"<b>₹{plan['price']}</b>\n"
            f"🆔 Request ID: "
            f"<code>{html.escape(str(payment_id))}</code>\n\n"
            "⏳ Status: <b>PENDING</b>\n\n"
            "Payment করার পরে Admin-কে এই Request ID পাঠাও।\n"
            "Admin verify করার পরে plan activate করবে।",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 BACK TO PLANS",
                        callback_data="dashboard:plans"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💳 WALLET",
                        callback_data="dashboard:wallet"
                    )
                ]
            ])
        )

        return

    # =========================================================
    # OLD PLANS SCREEN
    # =========================================================
    if data == "plans":

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        await safe_send(
            query.edit_message_text,
            plans_text(),
            parse_mode="HTML",
            reply_markup=plans_kb()
        )

        return

    # =========================================================
    # OLD WALLET SCREEN
    # =========================================================
    if data == "wallet":

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        ensure_wallet(user_id)

        claim_daily_spin(user_id)
        apply_daily_credit(user_id)

        await safe_send(
            query.edit_message_text,
            wallet_text(user_id),
            parse_mode="HTML",
            reply_markup=wallet_kb()
        )

        return

    # =========================================================
    # OLD SPIN SCREEN
    # =========================================================
    if data == "spin":

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        ensure_wallet(user_id)

        claim_daily_spin(user_id)

        await safe_send(
            query.edit_message_text,
            spin_text(user_id),
            parse_mode="HTML",
            reply_markup=spin_kb()
        )

        return

    # =========================================================
    # FREE SPIN ACTION
    # =========================================================
    if data == "spin_now":

        ensure_wallet(user_id)

        result = perform_free_spin(
            user_id
        )

        if result is None:

            await safe_send(
                query.edit_message_text,
                "🎰 <b>NO SPIN AVAILABLE</b>\n\n"
                "তোমার কাছে এখন কোনো free spin নেই।",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🎰 BACK TO SPIN",
                            callback_data="dashboard:spin"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "💳 WALLET",
                            callback_data="dashboard:wallet"
                        )
                    ],
                ])
            )

            return

        reward_type, reward_value = result

        if reward_type == "credits":

            reward_text = (
                f"💰 <b>+{reward_value} CREDITS</b>"
            )

        elif reward_type == "bonus_spin":

            reward_text = (
                "🎰 <b>+1 BONUS SPIN</b>"
            )

        else:

            reward_text = (
                "🎁 <b>Bonus received!</b>"
            )

        await safe_send(
            query.edit_message_text,
            "╔══════════════════════════╗\n"
            "       🎉 <b>SPIN RESULT</b>\n"
            "╚══════════════════════════╝\n\n"
            f"{reward_text}\n\n"
            "🎁 Free bonus spin completed.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🎰 SPIN AGAIN",
                        callback_data="dashboard:spin"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💳 WALLET",
                        callback_data="dashboard:wallet"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 DASHBOARD",
                        callback_data="dashboard:home"
                    )
                ],
            ])
        )

        return

    # =========================================================
    # OLD HISTORY SCREEN
    # =========================================================
    if data == "history":

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        try:

            history_text = transactions_text(
                user_id
            )

        except Exception:

            logger.exception(
                "History error for user %s",
                user_id
            )

            history_text = (
                "❌ <b>HISTORY ERROR</b>\n\n"
                "Unable to load your transaction "
                "history right now."
            )

        await safe_send(
            query.edit_message_text,
            history_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "💳 WALLET",
                        callback_data="dashboard:wallet"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💎 DASHBOARD",
                        callback_data="dashboard:home"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 MAIN MENU",
                        callback_data="main_menu"
                    )
                ]
            ])
        )

        return

    # =========================================================
    # VEHICLE SUB MENU
    # =========================================================
    if data == "sub:vehicle":

        context.user_data.pop("mode", None)

        await safe_send(
            query.edit_message_text,
            "🚗 <b>VEHICLE RC</b>\n\n"
            "<b>Choose version:</b>",
            parse_mode="HTML"
        )

        if query.message:

            await query.message.reply_text(
                "👇 Select Vehicle API version:",
                parse_mode="HTML",
                reply_markup=vehicle_kb()
            )

        return

    # =========================================================
    # IP SUB MENU
    # =========================================================
    if data == "sub:ip":

        context.user_data.pop("mode", None)

        await safe_send(
            query.edit_message_text,
            "🌐 <b>IP LOOKUP</b>\n\n"
            "<b>Choose version:</b>",
            parse_mode="HTML"
        )

        if query.message:

            await query.message.reply_text(
                "👇 Select IP API version:",
                parse_mode="HTML",
                reply_markup=ip_kb()
            )

        return

    # =========================================================
    # WEATHER SUB MENU
    # =========================================================
    if data == "sub:weather":

        context.user_data.pop("mode", None)

        await safe_send(
            query.edit_message_text,
            "🌦️ <b>WEATHER</b>\n\n"
            "<b>Choose option:</b>",
            parse_mode="HTML"
        )

        if query.message:

            await query.message.reply_text(
                "👇 Select Weather service:",
                parse_mode="HTML",
                reply_markup=weather_kb()
            )

        return

    # =========================================================
    # BOT STATUS
    # =========================================================
    if data == "q:status":

        context.user_data.pop("mode", None)

        uptime = max(
            0,
            int(time.time() - START_TIME)
        )

        text = (
            banner("📊 BOT STATUS") + "\n"
            f"🟢 Status: <b>Running</b>\n"
            f"⏱ Uptime: "
            f"<code>{uptime // 3600}h "
            f"{(uptime % 3600) // 60}m "
            f"{uptime % 60}s</code>\n"
            f"👥 Verified Users: "
            f"<code>{len(VERIFIED_USERS)}</code>\n"
            f"🛠 Tools: <code>{len(ACTIONS)}</code>\n"
            f"📡 API: <code>Connected</code>"
        )

        await safe_send(
            query.edit_message_text,
            text,
            parse_mode="HTML"
        )

        if query.message:

            await query.message.reply_text(
                "👇 Back to main menu:",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

        return

    # =========================================================
    # PREMIUM HELP
    # =========================================================
    if data == "q:help":

        context.user_data.pop("mode", None)

        text = (
            "🆘 <b>HELP MENU</b>\n\n"
            "🔍 Number Search\n"
            "🆔 Aadhar Info\n"
            "👤 Telegram Info\n"
            "📸 Instagram Info\n"
            "🚗 Vehicle RC (V1-V4)\n"
            "🌐 IP Lookup (V1-V3)\n"
            "🌦 Weather\n"
            "📱 IMEI\n"
            "📮 Pincode\n"
            "🏦 IFSC\n"
            "🌍 Country\n"
            "💳 UPI\n"
            "💰 Paytm\n\n"
            "<i>Use buttons or commands like "
            "/num, /v1, /upi etc.</i>"
        )

        await safe_send(
            query.edit_message_text,
            text,
            parse_mode="HTML"
        )

        if query.message:

            await query.message.reply_text(
                "👇 Back to main menu:",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

        return

    # =========================================================
    # NORMAL ACTIONS
    # =========================================================
    if data.startswith("q:"):

        action_id = data.split(
            ":",
            1
        )[1].strip()

        if action_id in ACTIONS:

            _, _, prompt, _ = ACTIONS[action_id]

            context.user_data["mode"] = action_id

            await safe_send(
                query.edit_message_text,
                prompt,
                parse_mode="HTML",
                reply_markup=back_kb()
            )

            return

    # =========================================================
    # MAIN MENU
    # =========================================================
    if data == "main_menu":

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        await safe_send(
            query.edit_message_text,
            banner("🏠 MAIN MENU"),
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )

        return

    # =========================================================
    # UNKNOWN CALLBACK
    # =========================================================
    logger.warning(
        "Unknown callback received: %s from user %s",
        data,
        user_id
    )

    await safe_send(
        query.edit_message_text,
        "⚠️ <b>Unknown action.</b>\n\n"
        "Please return to the main menu.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🏠 MAIN MENU",
                    callback_data="main_menu"
                )
            ]
        ])
    )




async def approve_payment_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id

    # =========================================================
    # ADMIN CHECK
    # =========================================================
    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ Admin access required."
        )
        return

    # =========================================================
    # PAYMENT ID CHECK
    # =========================================================
    if not context.args:
        await update.message.reply_text(
            "❌ Usage:\n"
            "/approve_payment <payment_id>"
        )
        return

    try:
        payment_id = int(context.args[0])
    except (ValueError, TypeError):
        await update.message.reply_text(
            "❌ Invalid payment ID."
        )
        return

    # =========================================================
    # ATOMIC APPROVAL
    # =========================================================
    try:
        success, status, target_user_id, plan_id = await asyncio.to_thread(
            approve_payment,
            payment_id
        )
    except Exception:
        logger.exception(
            "approve_payment crashed for payment %s",
            payment_id
        )

        await update.message.reply_text(
            "❌ Payment approval failed.\n\n"
            "⚠️ Internal error occurred.\n"
            "Please check the logs."
        )
        return

    # =========================================================
    # PAYMENT NOT FOUND
    # =========================================================
    if status == "not_found":
        await update.message.reply_text(
            f"❌ Payment #{payment_id} not found."
        )
        return

    # =========================================================
    # APPROVAL FAILED
    # IMPORTANT:
    # success আগে check হবে
    # =========================================================
    if not success:
        await update.message.reply_text(
            "❌ <b>Payment approval failed.</b>\n\n"
            f"🧾 Payment ID: <code>{payment_id}</code>\n"
            f"⚠️ Status: <b>{html.escape(str(status))}</b>\n\n"
            "Please check the logs.",
            parse_mode="HTML"
        )
        return

    # =========================================================
    # ALREADY PROCESSED / INVALID STATUS
    # =========================================================
    if status != "approved":
        await update.message.reply_text(
            f"⚠️ Payment #{payment_id} "
            f"is <b>{html.escape(str(status))}</b>.",
            parse_mode="HTML"
        )
        return

    # =========================================================
    # PLAN INFO
    # =========================================================
    plan = PLANS.get(plan_id)

    plan_name = (
        plan["name"]
        if plan
        else str(plan_id)
    )
    # =========================================
    # PLAN ACTIVATION USER NOTIFICATION
    # =========================================

    try:
        activated_plan = PLANS.get(
            plan_id,
            {}
        )

        activated_plan_name = activated_plan.get(
            "name",
            str(plan_id).upper()
        )

        activated_credits = activated_plan.get(
            "credits",
            0
        )

        activated_days = activated_plan.get(
            "duration_days"
        )

        if activated_days is None:
            expiry_text = "♾️ Lifetime"
        else:
            expiry_timestamp = time.time() + (
                int(activated_days) * 86400
            )

            expiry_text = datetime.fromtimestamp(
                expiry_timestamp,
                IST
            ).strftime("%d-%m-%Y %H:%M")

        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                "🎉 <b>PLAN ACTIVATED</b>\n\n"
                f"💎 Plan: <b>{html.escape(str(activated_plan_name))}</b>\n"
                f"🎁 Credits Added: <b>{activated_credits}</b>\n"
                f"⏰ Valid Until: <code>{expiry_text}</code>\n\n"
                "✅ Your payment has been approved successfully.\n"
                "🚀 Enjoy your plan!"
            ),
            parse_mode="HTML"
        )

    except Forbidden:
        logger.info(
            "Could not notify user %s about plan activation.",
            target_user_id
        )

    except Exception:
        logger.exception(
            "Plan activation notification failed for user %s",
            target_user_id
        )


    safe_plan_name = html.escape(
        str(plan_name)
    )

    # =========================================================
    # SUCCESS
    # =========================================================
    await update.message.reply_text(
        "╔══════════════════════════╗\n"
        "       ✅ <b>PAYMENT APPROVED</b>\n"
        "╚══════════════════════════╝\n\n"
        f"🧾 Payment ID: <code>{payment_id}</code>\n"
        f"👤 User ID: <code>{target_user_id}</code>\n"
        f"💎 Plan: <b>{safe_plan_name}</b>\n\n"
        "✅ Payment approved successfully.\n"
        "🎟️ Plan activated.\n"
        "💰 Starting credits added.",
        parse_mode="HTML"
    )

    # =========================================================
    # USER NOTIFICATION
    # =========================================================
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                "╔══════════════════════════╗\n"
                "       🎉 <b>PLAN ACTIVATED</b>\n"
                "╚══════════════════════════╝\n\n"
                f"💎 Plan: <b>{safe_plan_name}</b>\n"
                f"🧾 Payment ID: <code>{payment_id}</code>\n\n"
                "✅ Your payment has been approved.\n"
                "🎟️ Your plan is now active.\n\n"
                "💳 Open Wallet to check your credits."
            ),
            parse_mode="HTML"
        )

    except Exception:
        logger.exception(
            "Could not notify user %s about payment %s",
            target_user_id,
            payment_id
        )


async def wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id

    # =========================================================
    # USER REGISTER
    # =========================================================
    USER_IDS.add(user_id)
    db_add_user(user_id)

    # =========================================================
    # BAN CHECK
    # =========================================================
    if user_id in BANNED_USERS and not is_admin(user_id):
        await update.message.reply_text(
            "🚫 <b>You are banned from using this bot.</b>\n\n"
            "You cannot use wallet services.",
            parse_mode="HTML"
        )
        return

    # =========================================================
    # MAINTENANCE CHECK
    # =========================================================
    if MAINTENANCE_MODE and not is_admin(user_id):
        await update.message.reply_text(
            "🛠️ <b>BOT UNDER MAINTENANCE</b>\n\n"
            "Please try again later.",
            parse_mode="HTML"
        )
        return

    # =========================================================
    # CHANNEL JOIN CHECK
    # Adminদের channel verification লাগবে না
    # =========================================================
    if not is_admin(user_id):
        if not await is_member(context.bot, user_id):
            await update.message.reply_text(
                "❌ <b>Please join our channel first.</b>\n\n"
                "Join the channel and try again.",
                parse_mode="HTML",
                reply_markup=join_kb()
            )
            return

    # =========================================================
    # WALLET INIT
    # =========================================================
    ensure_wallet(user_id)

    # =========================================================
    # DAILY REWARDS
    # =========================================================
    claim_daily_spin(user_id)
    apply_daily_credit(user_id)

    # =========================================================
    # GET WALLET
    # =========================================================
    wallet = get_wallet(user_id)
    plan, expires_at = get_user_plan(user_id)

    # =========================================================
    # EXPIRY TIME
    # IST ব্যবহার করা হচ্ছে
    # =========================================================
    if expires_at:
        expiry = datetime.fromtimestamp(
            expires_at,
            IST
        ).strftime("%d-%m-%Y %H:%M")
    else:
        expiry = "NO EXPIRY"

    # =========================================================
    # WALLET TEXT
    # =========================================================
    text = (
        "╔══════════════════════════╗\n"
        "       💳 <b>MY WALLET</b>\n"
        "╚══════════════════════════╝\n\n"

        f"👤 User ID: <code>{user_id}</code>\n\n"

        f"📦 Plan: <b>{html.escape(str(plan).upper())}</b>\n"
        f"💰 Credits: <b>{wallet['credits']}</b>\n"
        f"🎁 Bonus: <b>{wallet['bonus_credits']}</b>\n"
        f"🎰 Spins: <b>{wallet['spins']}</b>\n"
        f"⏰ Expiry: <b>{html.escape(str(expiry))}</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "💎 <i>TRX EDITION</i>"
    )

    # =========================================================
    # SEND WALLET
    # =========================================================
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=back_kb()
    )


async def text_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    global MAINTENANCE_MODE

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BASIC MESSAGE VALIDATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if not update.message:
        return

    if not update.message.text:
        return

    if not update.effective_user:
        return

    text = update.message.text.strip()

    if not text:
        return

    user_id = update.effective_user.id

    USER_IDS.add(user_id)
    db_add_user(user_id)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BASIC ACCESS CONTROL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if user_id in BANNED_USERS and not is_admin(user_id):

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        await update.message.reply_text(
            "🚫 <b>You are banned from using this bot.</b>\n\n"
            "You cannot use any bot services.",
            parse_mode="HTML"
        )
        return

    if MAINTENANCE_MODE and not is_admin(user_id):

        context.user_data.pop("mode", None)
        context.user_data.pop("admin_mode", None)

        await update.message.reply_text(
            "🛠️ <b>BOT UNDER MAINTENANCE</b>\n\n"
            "Please try again later.",
            parse_mode="HTML"
        )
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BUTTON MAP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    button_map = {

        # PAGE 1
        "🔍  NUMBER SEARCH": "num",
        "🆔  AADHAR INFO": "aadhar",
        "💎  DASHBOARD": "dashboard",
        "💳 WALLET": "wallet",
        "⭐ PLANS": "plans",
        "🎰 SPIN": "spin",
        "📜 HISTORY": "history",
        "👤 MY PROFILE": "profile",
        "🎁 REFERRAL": "referral",
        "📊 MY USAGE": "user_usage",
        "💰 PAYMENT HISTORY": "user_payments",
        "🔔 NOTIFICATIONS": "user_notifications",
        "⚙️ SETTINGS": "user_settings",
        "🌐 SERVICE STATUS": "status",
        "❓ HELP & FAQ": "help",
        "📞 SUPPORT": "support",
        "🏠 MAIN PAGE": "main_page",
        "📱  TG TO NUMBER": "tgid_num",
        "👤  TELEGRAM INFO": "tg",
        "📸  INSTAGRAM INFO": "insta",
        "🚘  VEHICLE RC  ✦": "sub:vehicle",
        "➡️  NEXT PAGE": "next_page",

        # PAGE 2
        "🌐  IP LOOKUP  ✦": "sub:ip",
        "🌤️  WEATHER  ✦": "sub:weather",
        "📱  IMEI INFO": "imei",
        "📮  PINCODE INFO": "pin",
        "🏦  IFSC INFO": "ifsc",
        "⬅️  PREVIOUS": "previous_page",

        # PAGE 3
        "🌍  COUNTRY INFO": "country",
        "💳  UPI INFO": "upi",
        "💰  PAYTM INFO": "paytm",
        "📊  BOT STATUS": "status",
        "🆘  PREMIUM HELP": "help",
        "👤  MY PROFILE": "profile",
        "🎁  REFERRAL": "referral",
        "🏠  MAIN PAGE": "main_page",

        # VEHICLE
        "🚙  VEHICLE V1": "v1",
        "🚕  VEHICLE V2": "v2",
        "🛻  VEHICLE V3": "v3",
        "🏎  VEHICLE V4": "v4",

        # IP
        "🌐  IP V1": "ipv1",
        "🌐  IP V2": "ipv2",
        "🌐  IP V3": "ipv3",

        # WEATHER
        "🌤️  WEATHER SEARCH": "weather",
        "🌦️  WEATHER INFO": "weatherinfo",

        # COMMON
        "🔙  BACK TO MAIN": "main_menu",

        # ADMIN
        "📊 STATISTICS": "admin_stats",
        "👥 USERS": "admin_users",
        "🚫 BAN / UNBAN": "admin_ban",
        "💰 ADD CREDIT": "admin_add_credit",
        "📢 BROADCAST": "admin_broadcast",
        "🔧 MAINTENANCE": "admin_maintenance",
        "🔎 USER SEARCH": "admin_user_search",
        "🛡️ PROTECTION": "admin_protection",
        "💳 PAYMENTS": "admin_payments",
        "📡 API STATUS": "admin_api",
        "⚡ LIGHTSPEED": "admin_lightspeed",
        "🧰 MORE TOOLS": "admin_more_tools",
        "📋 LOGS": "admin_logs",
        "👥 GROUPS": "admin_groups",
        "💾 DB BACKUP": "admin_backup",
        "⚙️ SETTINGS": "admin_settings",
        "🔙 ADMIN BACK": "admin_back",
    }

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NORMALIZE BUTTON TEXT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    normalized_text = re.sub(
      r"\s+",
      " ",
      text.strip()
    )

    action = None

    for button_text, button_action in button_map.items():
      if re.sub(
        r"\s+",
        " ",
        button_text.strip()
      ) == normalized_text:
        action = button_action
        break

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ADMIN MODE SECURITY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    admin_mode = context.user_data.get(
        "admin_mode"
    )

    if admin_mode and not is_admin(user_id):

        context.user_data.pop(
            "admin_mode",
            None
        )

        context.user_data.pop(
            "mode",
            None
        )

        await update.message.reply_text(
            "⛔ <b>ACCESS DENIED</b>\n\n"
            "Admin access required.",
            parse_mode="HTML"
        )

        return

    if admin_mode == "broadcast" and is_admin(user_id):
        sent = failed = 0
        for target_id in get_saved_broadcast_targets():
            try:
                await context.bot.send_message(chat_id=target_id, text=text, parse_mode="HTML"); sent += 1; await asyncio.sleep(0.05)
            except RetryAfter as exc:
                await asyncio.sleep(float(getattr(exc, "retry_after", 1)) + 0.5)
            except Exception: failed += 1
        context.user_data.pop("admin_mode", None)
        add_log(user_id, f"Broadcast sent={sent} failed={failed}")
        await update.message.reply_text(f"📢 <b>BROADCAST COMPLETE</b>\n\n✅ Sent: <b>{sent}</b>\n❌ Failed: <b>{failed}</b>", parse_mode="HTML", reply_markup=admin_kb())
        return

    if admin_mode == "user_search" and is_admin(user_id):
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("❌ Send a valid numeric User ID.", reply_markup=admin_kb()); return
        target_id=int(text); profile=get_user_profile(target_id)
        if not profile:
            await update.message.reply_text("❌ <b>User not found.</b>", parse_mode="HTML", reply_markup=admin_kb()); context.user_data.pop("admin_mode",None); return
        wallet=get_wallet(target_id); plan,expires=get_user_plan(target_id); expiry=datetime.fromtimestamp(expires,IST).strftime("%d-%m-%Y %H:%M") if expires else "NO EXPIRY"
        username=f"@{profile[2]}" if profile[2] else "Not set"
        await update.message.reply_text(f"🔎 <b>USER DETAILS</b>\n\n🆔 <code>{target_id}</code>\n👤 {html.escape(str(profile[3] or 'Unknown'))}\n🔹 {html.escape(username)}\n💎 Plan: <b>{html.escape(str(plan).upper())}</b>\n💰 Credits: <b>{wallet['credits']}</b>\n🎁 Bonus: <b>{wallet['bonus_credits']}</b>\n👥 Referrals: <b>{get_referral_count(target_id)}</b>\n🚫 Banned: <b>{'YES' if target_id in BANNED_USERS else 'NO'}</b>\n⏰ Expiry: <b>{expiry}</b>", parse_mode="HTML", reply_markup=admin_kb())
        context.user_data.pop("admin_mode",None); return

    if admin_mode == "protection" and is_admin(user_id):
        parts=text.split(maxsplit=1)
        if len(parts)==2 and parts[0].lower() in {"id","username","number"}:
            ok=add_protected_entry(parts[1],parts[0].lower(),user_id)
            msg="✅ <b>Protected entry added.</b>" if ok else "❌ Could not add entry."
        elif len(parts)==2 and parts[0].lower()=="remove":
            msg="✅ Removed." if remove_protected_entry(parts[1]) else "❌ Entry not found."
        else:
            msg="🛡️ <b>Format</b>\n<code>id 123456789</code>\n<code>username @example</code>\n<code>number +911234567890</code>\n<code>remove VALUE</code>"
        context.user_data.pop("admin_mode",None); await update.message.reply_text(msg,parse_mode="HTML",reply_markup=admin_kb()); return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ADMIN ADD CREDIT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if admin_mode == "add_credit" and is_admin(user_id):

        parts = text.split()

        if len(parts) != 2:
            await update.message.reply_text(
                "❌ <b>Invalid Format</b>\n\n"
                "এই format-এ পাঠাও:\n\n"
                "<code>USER_ID AMOUNT</code>\n\n"
                "Example:\n"
                "<code>123456789 50</code>",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )
            return

        if not parts[0].isdigit() or not parts[1].isdigit():

            await update.message.reply_text(
                "❌ <b>Invalid Input</b>\n\n"
                "USER ID এবং CREDIT amount দুটোই number হতে হবে।\n\n"
                "Example:\n"
                "<code>123456789 50</code>",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )
            return

        target_id = int(parts[0])
        amount = int(parts[1])

        if target_id <= 0 or amount <= 0:

            await update.message.reply_text(
                "❌ <b>Invalid User ID / Amount</b>",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )
            return

        success = add_credits(
            target_id,
            amount,
            tx_type="admin_bonus",
            note=f"Added by admin {user_id}"
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        if not success:
            await update.message.reply_text(
                "❌ <b>Credit Add Failed</b>\n\n"
                "Credit দেওয়া যায়নি।",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )
            return

        wallet = get_wallet(target_id)
        new_balance = wallet["credits"]

        add_log(
            user_id,
            f"Added {amount} credits to user {target_id}"
        )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # USER CREDIT NOTIFICATION
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        try:

            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "╔══════════════════════════╗\n"
                    "       💰 <b>CREDIT ADDED</b>\n"
                    "╚══════════════════════════╝\n\n"
                    f"➕ Added: <b>{amount}</b> credits\n\n"
                    f"💰 New Balance: <b>{new_balance}</b> credits\n\n"
                    "👑 Credits were added by an administrator.\n"
                    "✅ You can now use your available services."
                ),
                parse_mode="HTML"
            )

        except Forbidden:

            logger.info(
                "User %s blocked the bot. "
                "Credit notification skipped.",
                target_id
            )

        except Exception:

            logger.exception(
                "Failed to send credit notification "
                "to user %s",
                target_id
            )

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # ADMIN SUCCESS MESSAGE
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        await update.message.reply_text(
            "╔══════════════════════════╗\n"
            "       💰 <b>CREDIT ADDED</b>\n"
            "╚══════════════════════════╝\n\n"
            f"👤 User ID:\n"
            f"<code>{target_id}</code>\n\n"
            f"➕ Added:\n"
            f"<b>{amount}</b> credits\n\n"
            f"💰 New Balance:\n"
            f"<b>{new_balance}</b> credits\n\n"
            "📩 User notification sent.",
            parse_mode="HTML",
            reply_markup=admin_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ADMIN BAN / UNBAN
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if admin_mode == "ban" and is_admin(user_id):

        if not text.isdigit():

            await update.message.reply_text(
                "❌ <b>Invalid User ID</b>\n\n"
                "শুধু numeric Telegram User ID পাঠাও।\n\n"
                "Example:\n"
                "<code>123456789</code>",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return

        target_id = int(text)

        if target_id <= 0:

            await update.message.reply_text(
                "❌ <b>Invalid User ID</b>",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return

        if target_id in ADMIN_IDS:

            context.user_data.pop(
                "admin_mode",
                None
            )

            await update.message.reply_text(
                "⛔ <b>Admin account ban করা যাবে না।</b>",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return

        if target_id in BANNED_USERS:

            BANNED_USERS.remove(
                target_id
            )

            db_unban_user(
                target_id
            )

            status = "🟢 UNBANNED"

            log_action = (
                f"Unbanned user {target_id}"
            )

        else:

            BANNED_USERS.add(
                target_id
            )

            db_ban_user(
                target_id
            )

            status = "🚫 BANNED"

            log_action = (
                f"Banned user {target_id}"
            )

        context.user_data.pop(
            "admin_mode",
            None
        )

        add_log(
            user_id,
            log_action
        )

        await update.message.reply_text(
            "╔══════════════════════════╗\n"
            "       🚫 <b>USER CONTROL</b>\n"
            "╚══════════════════════════╝\n\n"
            f"👤 User ID:\n"
            f"<code>{target_id}</code>\n\n"
            f"Status: <b>{status}</b>",
            parse_mode="HTML",
            reply_markup=admin_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ADMIN PANEL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action and action.startswith("admin_"):

        if not is_admin(user_id):

            await update.message.reply_text(
                "⛔ <b>ACCESS DENIED</b>",
                parse_mode="HTML"
            )

            return

        # ─────────────────────────────
        # STATISTICS
        # ─────────────────────────────

        if action == "admin_stats":

            uptime = max(
                0,
                int(time.time() - START_TIME)
            )

            hours = uptime // 3600

            minutes = (
                (uptime % 3600) // 60
            )

            seconds = uptime % 60

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # DATABASE STATISTICS
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            with DB_LOCK:
                conn = sqlite3.connect(DB_FILE)

                service_rows = conn.execute(
                    "SELECT action, COUNT(*) "
                    "FROM logs "
                    "WHERE action LIKE '% request' "
                    "GROUP BY action "
                    "ORDER BY COUNT(*) DESC "
                    "LIMIT 5"
                ).fetchall()

                active_plans = conn.execute("""
                    SELECT COUNT(*)
                    FROM subscriptions
                    WHERE status = 'active'
                """).fetchone()[0]

                pending_payments = conn.execute("""
                    SELECT COUNT(*)
                    FROM payments
                    WHERE status = 'pending'
                """).fetchone()[0]

                approved_payments = conn.execute("""
                    SELECT COUNT(*)
                    FROM payments
                    WHERE status = 'approved'
                """).fetchone()[0]

                group_count = conn.execute(
                    "SELECT COUNT(*) FROM bot_groups"
                ).fetchone()[0]

                conn.close()

            service_text = (
                "\n".join(
                    f"• {html.escape(str(a).replace(' request', ''))}: "
                    f"<b>{c}</b>"
                    for a, c in service_rows
                )
                or "• No data yet"
            )

            stats_text = (
                "╔══════════════════════════╗\n"
                "   📊 <b>BOT STATISTICS</b>\n"
                "╚══════════════════════════╝\n\n"

                "🤖 Status: <b>🟢 ONLINE</b>\n"

                f"⏱ Uptime: "
                f"<code>{hours}h "
                f"{minutes}m "
                f"{seconds}s</code>\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n"
                "👥 <b>USER DATA</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"👤 Total Users: "
                f"<code>{len(USER_IDS)}</code>\n"

                f"✅ Verified Users: "
                f"<code>{len(VERIFIED_USERS)}</code>\n"

                f"🚫 Banned Users: "
                f"<code>{len(BANNED_USERS)}</code>\n"

                f"👑 Admins: "
                f"<code>{len(ADMIN_IDS)}</code>\n"

                f"👥 Registered Groups: "
                f"<code>{group_count}</code>\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n"
                "💎 <b>SUBSCRIPTION DATA</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"💎 Active Plans: "
                f"<code>{active_plans}</code>\n"

                f"⏳ Pending Payments: "
                f"<code>{pending_payments}</code>\n"

                f"✅ Approved Payments: "
                f"<code>{approved_payments}</code>\n\n"

                "━━━━━━━━━━━━━━━━━━━━\n"
                "📡 <b>BOT ACTIVITY</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"📊 Total Requests: "
                f"<code>{REQUEST_COUNT}</code>\n"

                f"📋 Stored Logs: "
                f"<code>{len(ACTIVITY_LOGS)}</code>\n"

                f"🛠 Available Tools: "
                f"<code>{len(ACTIONS)}</code>\n\n"

                "📈 <b>TOP SERVICES</b>\n"
                f"{service_text}\n"

                "━━━━━━━━━━━━━━━━━━━━\n"

                f"🔧 Maintenance: "
                f"<b>{'ON' if MAINTENANCE_MODE else 'OFF'}</b>"
            )

            await safe_send(
                update.message.reply_text,
                stats_text,
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return

        # ─────────────────────────────
        # USERS
        # ─────────────────────────────

        if action == "admin_users":

            uptime = max(
                0,
                int(time.time() - START_TIME)
            )

            hours = uptime // 3600

            minutes = (
                (uptime % 3600) // 60
            )

            seconds = uptime % 60

            recent_logs = ACTIVITY_LOGS[-5:]

            if recent_logs:

                recent_text = ""

                for log in recent_logs:

                    recent_text += (
                        f"👤 <code>{log['user_id']}</code>  "
                        f"⚡ "
                        f"{html.escape(str(log['action']))}\n"
                        f"   🕐 "
                        f"{html.escape(str(log['time']))}\n"
                    )

            else:

                recent_text = (
                    "📭 No recent activity."
                )

            users_text = (
                "╔══════════════════════════╗\n"
                "     👥 <b>USERS</b>\n"
                "╚══════════════════════════╝\n\n"

                "📊 <b>USER OVERVIEW</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"👤 Total Users: "
                f"<code>{len(USER_IDS)}</code>\n"

                f"✅ Verified Users: "
                f"<code>{len(VERIFIED_USERS)}</code>\n"

                f"🚫 Banned Users: "
                f"<code>{len(BANNED_USERS)}</code>\n"

                f"👑 Admins: "
                f"<code>{len(ADMIN_IDS)}</code>\n\n"

                "📈 <b>BOT ACTIVITY</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"

                f"📡 Requests: "
                f"<code>{REQUEST_COUNT}</code>\n"

                f"📋 Stored Logs: "
                f"<code>{len(ACTIVITY_LOGS)}</code>\n"

                f"⏱ Uptime: "
                f"<code>{hours}h "
                f"{minutes}m "
                f"{seconds}s</code>\n\n"

                "🕘 <b>RECENT ACTIVITY</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"{recent_text}"
            )

            await safe_send(
                update.message.reply_text,
                users_text,
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return

        if action == "admin_payments":
            with DB_LOCK:
                conn = sqlite3.connect(DB_FILE)
                rows = conn.execute("SELECT id, user_id, plan, amount, currency, created_at FROM payments WHERE status = 'pending' ORDER BY id DESC LIMIT 20").fetchall()
                conn.close()
            if not rows:
                payment_text = "💳 <b>PENDING PAYMENTS</b>\n\n📭 No pending payments."
            else:
                lines=["💳 <b>PENDING PAYMENTS</b>\n"]
                for pid, uid, plan, amount, currency, created in rows:
                    dt=datetime.fromtimestamp(float(created), IST).strftime("%d-%m-%Y %H:%M")
                    lines.append(f"🧾 <code>#{pid}</code> | 👤 <code>{uid}</code>\n⭐ {html.escape(str(plan))} | 💰 {amount:g} {html.escape(str(currency))}\n🕐 {dt}\n")
                payment_text="\n".join(lines)
            await update.message.reply_text(payment_text, parse_mode="HTML", reply_markup=admin_kb())
            return

        if action == "admin_user_search":
            context.user_data["admin_mode"]="user_search"
            await update.message.reply_text("🔎 <b>USER SEARCH</b>\n\nSend User ID:",parse_mode="HTML",reply_markup=admin_kb()); return

        if action == "admin_protection":
            context.user_data["admin_mode"]="protection"
            await update.message.reply_text("🛡️ <b>PROTECTION MANAGER</b>\n\n<code>id 123456789</code>\n<code>username @example</code>\n<code>number +911234567890</code>\n<code>remove VALUE</code>",parse_mode="HTML",reply_markup=admin_kb()); return

        # ─────────────────────────────
        # ADD CREDIT
        # ─────────────────────────────

        if action == "admin_add_credit":

            context.user_data.pop(
                "mode",
                None
            )

            context.user_data[
                "admin_mode"
            ] = "add_credit"

            await update.message.reply_text(
                "╔══════════════════════════╗\n"
                "       💰 <b>ADD CREDIT</b>\n"
                "╚══════════════════════════╝\n\n"
                "User ID এবং কত credit দিতে চাও\n"
                "একই message-এ পাঠাও।\n\n"
                "Format:\n"
                "<code>USER_ID AMOUNT</code>\n\n"
                "Example:\n"
                "<code>123456789 50</code>",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return



        # ─────────────────────────────
        # BAN / UNBAN
        # ─────────────────────────────

        if action == "admin_ban":

            context.user_data.pop(
                "mode",
                None
            )

            context.user_data[
                "admin_mode"
            ] = "ban"

            await update.message.reply_text(
                "🚫 <b>BAN / UNBAN USER</b>\n\n"
                "User ID পাঠাও:\n\n"
                "Example:\n"
                "<code>123456789</code>",
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return

        # ─────────────────────────────
        # MAINTENANCE
        # ─────────────────────────────

        if action == "admin_maintenance":

          MAINTENANCE_MODE = not MAINTENANCE_MODE

          status = (
            "🟢 ON"
            if MAINTENANCE_MODE
            else "🔴 OFF"
          )

          context.user_data.pop(
            "admin_mode",
            None
          )

          context.user_data.pop(
            "mode",
            None
          )

          # =========================================
          # NOTIFY ALL SAVED DATABASE USERS
          # =========================================

          if MAINTENANCE_MODE:

            notification = (
              "🚨 <b>BOT MAINTENANCE STARTED</b>\n\n"
              "🔧 Status: <b>ON</b>\n"
              "⛔ Bot is temporarily under maintenance.\n\n"
              "Please try again later."
            )

          else:

            notification = (
              "✅ <b>BOT MAINTENANCE ENDED</b>\n\n"
              "🔧 Status: <b>OFF</b>\n"
              "🟢 Bot services are available again.\n\n"
              "Thank you for your patience."
            )

          sent = 0
          failed = 0

          # Database-এর users table থেকে সবাইকে নেওয়া হবে
          for target_id in get_saved_broadcast_targets():

            try:

              await context.bot.send_message(
                chat_id=target_id,
                text=notification,
                parse_mode="HTML"
              )

              sent += 1

              # Telegram flood-control এড়াতে
              await asyncio.sleep(0.05)

            except RetryAfter as exc:

              await asyncio.sleep(
                float(
                  getattr(
                    exc,
                    "retry_after",
                    1
                  )
                ) + 0.5
              )

              try:

                await context.bot.send_message(
                  chat_id=target_id,
                  text=notification,
                  parse_mode="HTML"
                )

                sent += 1

              except Exception:

                failed += 1

            except Exception:

              failed += 1

          await update.message.reply_text(
            "🔧 <b>MAINTENANCE MODE</b>\n\n"
            f"Current Status: <b>{status}</b>\n\n"
            "📢 <b>Notification Broadcast</b>\n"
            f"✅ Sent: <b>{sent}</b>\n"
            f"❌ Failed: <b>{failed}</b>",
            parse_mode="HTML",
            reply_markup=admin_kb()
          )

          return

        # ─────────────────────────────
        # LIGHTSPEED DASHBOARD
        # ─────────────────────────────

        if action == "admin_more_tools":
            await update.message.reply_text(
                admin_extra_text(),
                parse_mode="HTML",
                reply_markup=admin_extra_kb()
            )
            return

        if action == "admin_lightspeed":
            with DB_LOCK:
                conn = sqlite3.connect(DB_FILE)
                try:
                    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    verified = conn.execute("SELECT COUNT(*) FROM verified_users").fetchone()[0]
                    groups = conn.execute("SELECT COUNT(*) FROM bot_groups").fetchone()[0]
                    active_plans = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active'").fetchone()[0]
                    today_key = datetime.now(IST).strftime("%Y-%m-%d")
                    active_today = conn.execute("SELECT COUNT(DISTINCT user_id) FROM logs WHERE log_time LIKE ?", (today_key + "%",)).fetchone()[0]
                finally:
                    conn.close()
            with API_METRICS_LOCK:
                m = dict(API_METRICS)
            avg_ms = (m["total_ms"] / m["total"]) if m["total"] else 0
            success_rate = (m["success"] * 100 / m["total"]) if m["total"] else 0
            h = int(time.time() - START_TIME)
            health_age = int(time.time() - HEALTH_STATE["checked_at"]) if HEALTH_STATE["checked_at"] else None
            health_line = HEALTH_STATE["status"]
            if HEALTH_STATE["latency_ms"] is not None:
                health_line += f" • {HEALTH_STATE['latency_ms']:.0f} ms"
            await update.message.reply_text(
                "╔══════════════════════════╗\n"
                "      ⚡ <b>LIGHTSPEED DASHBOARD</b>\n"
                "╚══════════════════════════╝\n\n"
                f"🤖 Status: <b>ONLINE</b>\n"
                f"⏱ Uptime: <code>{h//3600}h {(h%3600)//60}m {h%60}s</code>\n\n"
                "📊 <b>LIVE OVERVIEW</b>\n"
                f"👤 Users: <code>{total_users}</code>\n"
                f"🟢 Active today: <code>{active_today}</code>\n"
                f"✅ Verified: <code>{verified}</code>\n"
                f"💎 Active plans: <code>{active_plans}</code>\n"
                f"👥 Groups: <code>{groups}</code>\n"
                f"🔎 Requests: <code>{REQUEST_COUNT}</code>\n\n"
                "📡 <b>API PERFORMANCE</b>\n"
                f"🟢 Success: <code>{m['success']}</code>\n"
                f"🔴 Failed: <code>{m['failed']}</code>\n"
                f"📈 Success rate: <code>{success_rate:.1f}%</code>\n"
                f"⚡ Avg latency: <code>{avg_ms:.0f} ms</code>\n"
                f"🕐 Last request: <code>{m['last_ms']:.0f} ms</code>\n"
                f"🧩 Last action: <code>{html.escape(m['last_action'])}</code>\n\n"
                f"🩺 Health probe: <b>{health_line}</b>"
                + (f"\n🕐 Checked: <code>{health_age}s ago</code>" if health_age is not None else "") ,
                parse_mode="HTML", reply_markup=admin_kb()
            )
            return

        # ─────────────────────────────
        # LOGS
        # ─────────────────────────────

        if action == "admin_logs":

            if not ACTIVITY_LOGS:

                log_text = (
                    "📋 No activity logs yet."
                )

            else:

                log_text = (
                    "📋 <b>RECENT ACTIVITY</b>\n\n"
                )

                for log in ACTIVITY_LOGS[-10:]:

                    log_text += (
                        f"👤 <code>{log['user_id']}</code>\n"
                        f"⚡ "
                        f"{html.escape(str(log['action']))}\n"
                        f"🕐 "
                        f"{html.escape(str(log['time']))}\n\n"
                    )

            await safe_send(
                update.message.reply_text,
                log_text,
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return

        # ─────────────────────────────
        # DATABASE BACKUP
        # ─────────────────────────────

        if action == "admin_backup":
            if not is_admin(user_id):
                await update.message.reply_text(
                    "⛔ <b>ACCESS DENIED</b>",
                    parse_mode="HTML"
                )
                return

            if not os.path.exists(DB_FILE):
                await update.message.reply_text(
                    "⚠️ Database file not found.",
                    reply_markup=admin_kb()
                )
                return

            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now(IST).strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"bot_backup_{stamp}.db")

            try:
                with DB_LOCK:
                    src = sqlite3.connect(DB_FILE)
                    dst = sqlite3.connect(backup_path)
                    with dst:
                        src.backup(dst)
                    dst.close()
                    src.close()

                add_log(user_id, "Created database backup")

                await update.message.reply_document(
                    document=open(backup_path, "rb"),
                    caption=(
                        "💾 <b>DATABASE BACKUP</b>\n\n"
                        f"🕐 {html.escape(stamp)}\n"
                        "✅ Backup created successfully."
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                logger.exception("Database backup failed")
                await update.message.reply_text(
                    "❌ <b>Backup failed.</b> Check the bot logs.",
                    parse_mode="HTML",
                    reply_markup=admin_kb()
                )
            finally:
                try:
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                except Exception:
                    logger.exception("Failed to remove temporary backup")

            return

        # ─────────────────────────────
        # GROUPS
        # ─────────────────────────────

        if action == "admin_groups":
            await update.message.reply_text(
                groups_text(),
                parse_mode="HTML",
                reply_markup=groups_kb()
            )
            return

        # ─────────────────────────────
        # SETTINGS
        # ─────────────────────────────

        if action == "admin_settings":

            settings_text = (
                "╔══════════════════════════╗\n"
                "         ⚙️ <b>SETTINGS</b>\n"
                "╚══════════════════════════╝\n\n"

                f"🔧 Maintenance: "
                f"<b>{'ON' if MAINTENANCE_MODE else 'OFF'}</b>\n"

                f"👑 Admin Count: "
                f"<b>{len(ADMIN_IDS)}</b>\n"

                f"📢 Channel: "
                f"<code>{html.escape(str(CHANNEL_ID))}</code>\n\n"

                "🔐 API credentials are hidden for security."
            )

            await safe_send(
                update.message.reply_text,
                settings_text,
                parse_mode="HTML",
                reply_markup=admin_kb()
            )

            return

        # ─────────────────────────────
        # API STATUS
        # ─────────────────────────────

        if action == "admin_api":
            with API_METRICS_LOCK:
                m = dict(API_METRICS)
            avg_ms = (m["total_ms"] / m["total"]) if m["total"] else 0
            success_rate = (m["success"] * 100 / m["total"]) if m["total"] else 0
            checked = HEALTH_STATE["checked_at"]
            age = int(time.time() - checked) if checked else None
            await update.message.reply_text(
                "📡 <b>API STATUS</b>\n\n"
                f"🩺 Health: <b>{html.escape(HEALTH_STATE['status'])}</b>\n"
                f"⏱ Probe latency: <code>{HEALTH_STATE['latency_ms'] if HEALTH_STATE['latency_ms'] is not None else 'N/A'} ms</code>\n"
                f"📟 HTTP: <code>{HEALTH_STATE['http_status'] if HEALTH_STATE['http_status'] is not None else 'N/A'}</code>\n"
                f"📈 Success rate: <code>{success_rate:.1f}%</code>\n"
                f"⚡ Avg request: <code>{avg_ms:.0f} ms</code>\n"
                f"🔢 Requests tracked: <code>{m['total']}</code>\n"
                + (f"🕐 Last probe: <code>{age}s ago</code>\n" if age is not None else "") +
                "\n🔐 API Key: <b>HIDDEN</b>\n"
                "🌐 Endpoint: <b>CONFIGURED</b>",
                parse_mode="HTML", reply_markup=admin_kb()
            )
            return

        # ─────────────────────────────
        # BROADCAST
        # ─────────────────────────────

        if action == "admin_broadcast":
            context.user_data["admin_mode"]="broadcast"
            await update.message.reply_text("📢 <b>BROADCAST</b>\n\nSend the message to broadcast.\nHTML is supported.",parse_mode="HTML",reply_markup=admin_kb())
            return

        # ─────────────────────────────
        # ADMIN BACK
        # ─────────────────────────────

        if action == "admin_back":

            context.user_data.pop(
                "admin_mode",
                None
            )

            context.user_data.pop(
                "mode",
                None
            )

            context.user_data[
                "menu_page"
            ] = 1

            await update.message.reply_text(
                "🏠 <b>Main Menu</b>",
                parse_mode="HTML",
                reply_markup=main_menu_kb(1)
            )

            return

    if action == "profile":
        await profile_cmd(update, context)
        return

    if action == "referral":
        await referral_cmd(update, context)
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # YOUR DASHBOARD
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "dashboard":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        if not is_admin(user_id):

            try:

                member_ok = await is_member(
                    context.bot,
                    user_id
                )

            except Exception:

                logger.exception(
                    "Dashboard channel verification failed "
                    "for user %s",
                    user_id
                )

                member_ok = False

            if not member_ok:

                await update.message.reply_text(
                    "❌ <b>Channel verification required.</b>\n\n"
                    "Please join the channel first.",
                    parse_mode="HTML",
                    reply_markup=join_kb()
                )

                return

            VERIFIED_USERS.add(
                user_id
            )

            db_verify_user(
                user_id
            )

        ensure_wallet(
            user_id
        )

        claim_daily_spin(
            user_id
        )

        apply_daily_credit(
            user_id
        )

        dashboard_text = (
            "╔══════════════════════════╗\n"
            "       💎 <b>YOUR DASHBOARD</b>\n"
            "╚══════════════════════════╝\n\n"

            f"👤 User ID: <code>{user_id}</code>\n\n"

            "💳 <b>WALLET</b>\n"
            "Check credits, bonus & expiry\n\n"

            "⭐ <b>PLANS</b>\n"
            "View available subscription plans\n\n"

            "🎰 <b>SPIN</b>\n"
            "Use your available free spin\n\n"

            "📜 <b>HISTORY</b>\n"
            "View your credit transactions\n\n"

            "━━━━━━━━━━━━━━━━━━━━\n"
            "👇 <b>Select an option below</b>"
        )

        await safe_send(
            update.message.reply_text,
            dashboard_text,
            parse_mode="HTML",
            reply_markup=user_dashboard_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # USER DASHBOARD EXTRA FEATURES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "user_usage":
        day_start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        with DB_LOCK:
            conn = sqlite3.connect(DB_FILE)
            try:
                total = conn.execute("SELECT COUNT(*) FROM logs WHERE user_id = ?", (user_id,)).fetchone()[0]
                today = conn.execute("SELECT COUNT(*) FROM logs WHERE user_id = ? AND created_at >= ?", (user_id, day_start)).fetchone()[0]
                tx = conn.execute("SELECT COUNT(*) FROM credit_transactions WHERE user_id = ?", (user_id,)).fetchone()[0]
            finally:
                conn.close()
        await update.message.reply_text(
            "📊 <b>MY USAGE</b>\n\n"
            f"📅 Today: <code>{today}</code>\n"
            f"📈 Total requests: <code>{total}</code>\n"
            f"💳 Credit transactions: <code>{tx}</code>\n\n"
            "🔒 Only your own activity is shown.",
            parse_mode="HTML", reply_markup=user_dashboard_kb()
        )
        return

    if action == "user_payments":
        with DB_LOCK:
            conn = sqlite3.connect(DB_FILE)
            try:
                rows = conn.execute(
                    "SELECT id, plan, amount, currency, status, created_at FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                    (user_id,)
                ).fetchall()
            finally:
                conn.close()
        if rows:
            lines = ["💰 <b>MY PAYMENT HISTORY</b>", "━━━━━━━━━━━━━━━━━━━━"]
            for pid, plan, amount, currency, status, created_at in rows:
                dt = datetime.fromtimestamp(created_at, IST).strftime("%d %b %Y %H:%M")
                lines.append(f"🧾 <code>#{pid}</code> • {html.escape(str(plan))} • {html.escape(str(amount))} {html.escape(str(currency))}\n   Status: <b>{html.escape(str(status).upper())}</b> • {dt}")
            text = "\n".join(lines)
        else:
            text = "💰 <b>MY PAYMENT HISTORY</b>\n\n📭 No payment records found."
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=user_dashboard_kb())
        return

    if action == "user_notifications":
        with DB_LOCK:
            conn = sqlite3.connect(DB_FILE)
            try:
                count = conn.execute("SELECT COUNT(*) FROM expiry_notifications WHERE user_id = ?", (user_id,)).fetchone()[0]
            finally:
                conn.close()
        await update.message.reply_text(
            "🔔 <b>NOTIFICATIONS</b>\n\n"
            "✅ Account notifications: <b>ON</b>\n"
            f"📬 Expiry notices recorded: <code>{count}</code>\n\n"
            "Important account/service notices will appear here when available.",
            parse_mode="HTML", reply_markup=user_dashboard_kb()
        )
        return

    if action == "user_settings":
        await update.message.reply_text(
            "⚙️ <b>USER SETTINGS</b>\n\n"
            "🔔 Notifications: <b>ON</b>\n"
            "📱 Mobile UI: <b>ON</b>\n"
            "🛡️ Privacy: <b>Personal data only</b>\n\n"
            "More preferences can be added here in future updates.",
            parse_mode="HTML", reply_markup=user_dashboard_kb()
        )
        return

    if action == "support":
        await update.message.reply_text(
            "📞 <b>SUPPORT</b>\n\n"
            "For account, subscription or technical help, please contact the bot administrator through the official support channel.",
            parse_mode="HTML", reply_markup=user_dashboard_kb()
        )
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # WALLET TEXT BUTTON
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "wallet":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        if not is_admin(user_id):

            try:

                member_ok = await is_member(
                    context.bot,
                    user_id
                )

            except Exception:

                logger.exception(
                    "Wallet channel verification failed "
                    "for user %s",
                    user_id
                )

                member_ok = False

            if not member_ok:

                await update.message.reply_text(
                    "❌ <b>Channel verification required.</b>\n\n"
                    "Please join the channel first.",
                    parse_mode="HTML",
                    reply_markup=join_kb()
                )

                return

        ensure_wallet(
            user_id
        )

        claim_daily_spin(
            user_id
        )

        apply_daily_credit(
            user_id
        )

        await safe_send(
            update.message.reply_text,
            wallet_text(user_id),
            parse_mode="HTML",
            reply_markup=wallet_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PLANS TEXT BUTTON
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "plans":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        if not is_admin(user_id):

            try:

                member_ok = await is_member(
                    context.bot,
                    user_id
                )

            except Exception:

                logger.exception(
                    "Plans channel verification failed "
                    "for user %s",
                    user_id
                )

                member_ok = False

            if not member_ok:

                await update.message.reply_text(
                    "❌ <b>Channel verification required.</b>\n\n"
                    "Please join the channel first.",
                    parse_mode="HTML",
                    reply_markup=join_kb()
                )

                return

        await safe_send(
            update.message.reply_text,
            plans_text(),
            parse_mode="HTML",
            reply_markup=plans_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SPIN TEXT BUTTON
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "spin":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        if not is_admin(user_id):

            try:

                member_ok = await is_member(
                    context.bot,
                    user_id
                )

            except Exception:

                logger.exception(
                    "Spin channel verification failed "
                    "for user %s",
                    user_id
                )

                member_ok = False

            if not member_ok:

                await update.message.reply_text(
                    "❌ <b>Channel verification required.</b>\n\n"
                    "Please join the channel first.",
                    parse_mode="HTML",
                    reply_markup=join_kb()
                )

                return

        ensure_wallet(
            user_id
        )

        claim_daily_spin(
            user_id
        )

        await safe_send(
            update.message.reply_text,
            spin_text(user_id),
            parse_mode="HTML",
            reply_markup=spin_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HISTORY TEXT BUTTON
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "history":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        if not is_admin(user_id):

            try:

                member_ok = await is_member(
                    context.bot,
                    user_id
                )

            except Exception:

                logger.exception(
                    "History channel verification failed "
                    "for user %s",
                    user_id
                )

                member_ok = False

            if not member_ok:

                await update.message.reply_text(
                    "❌ <b>Channel verification required.</b>\n\n"
                    "Please join the channel first.",
                    parse_mode="HTML",
                    reply_markup=join_kb()
                )

                return

        try:

            history_text = transactions_text(
                user_id
            )

        except Exception:

            logger.exception(
                "History error for user %s",
                user_id
            )

            history_text = (
                "❌ <b>HISTORY ERROR</b>\n\n"
                "Unable to load your transaction "
                "history right now."
            )

        await safe_send(
            update.message.reply_text,
            history_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "💳 WALLET",
                        callback_data="dashboard:wallet"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "💎 DASHBOARD",
                        callback_data="dashboard:home"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🏠 MAIN MENU",
                        callback_data="main_menu"
                    )
                ]
            ])
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PAGINATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "next_page":

        current_page = context.user_data.get(
            "menu_page",
            1
        )

        try:

            current_page = int(
                current_page
            )

        except (
            TypeError,
            ValueError
        ):

            current_page = 1

        current_page = min(
            current_page + 1,
            3
        )

        context.user_data[
            "menu_page"
        ] = current_page

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "      💎 <b>TRX PREMIUM</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            f"📄 <b>PAGE {current_page}/3</b>\n\n"
            "👇 Select your service:",
            parse_mode="HTML",
            reply_markup=main_menu_kb(
                current_page
            )
        )

        return

    if action == "previous_page":

        current_page = context.user_data.get(
            "menu_page",
            1
        )

        try:

            current_page = int(
                current_page
            )

        except (
            TypeError,
            ValueError
        ):

            current_page = 1

        current_page = max(
            current_page - 1,
            1
        )

        context.user_data[
            "menu_page"
        ] = current_page

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "      💎 <b>TRX PREMIUM</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            f"📄 <b>PAGE {current_page}/3</b>\n\n"
            "👇 Select your service:",
            parse_mode="HTML",
            reply_markup=main_menu_kb(
                current_page
            )
        )

        return

    if action == "main_page":

        context.user_data[
            "menu_page"
        ] = 1

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "      💎 <b>TRX PREMIUM</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            "🏠 <b>MAIN DASHBOARD</b>\n\n"
            "⚡ Fast Service\n"
            "💎 Premium Experience\n"
            "🛡️ Verified Access\n\n"
            "👇 Select your service:",
            parse_mode="HTML",
            reply_markup=main_menu_kb(1)
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # MAIN MENU
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "main_menu":

        context.user_data[
            "menu_page"
        ] = 1

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "     💎 <b>TRX VIP PANEL</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            "🏠 <b>MAIN MENU</b>\n\n"
            "⚡ Fast Service\n"
            "💎 Premium Experience\n"
            "🛡️ Verified Access\n\n"
            "👇 Select your premium service:",
            parse_mode="HTML",
            reply_markup=main_menu_kb(1)
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # VEHICLE SUB MENU
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "sub:vehicle":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "      🚗 <b>VEHICLE RC</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            "💎 <b>PREMIUM VEHICLE SERVICE</b>\n"
            "⚡ Select your API version below:",
            parse_mode="HTML",
            reply_markup=vehicle_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # IP SUB MENU
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "sub:ip":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "       🌐 <b>IP LOOKUP</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            "💎 <b>PREMIUM IP SERVICE</b>\n"
            "⚡ Select your API version below:",
            parse_mode="HTML",
            reply_markup=ip_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # WEATHER SUB MENU
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "sub:weather":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "        🌦️ <b>WEATHER</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            "💎 <b>PREMIUM WEATHER SERVICE</b>\n"
            "⚡ Select your service below:",
            parse_mode="HTML",
            reply_markup=weather_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STATUS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "status":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        uptime = max(
            0,
            int(time.time() - START_TIME)
        )

        status_text = (
            "╔════════════════════════╗\n"
            "       📊 <b>BOT STATUS</b>\n"
            "╚════════════════════════╝\n\n"

            "🟢 <b>Status:</b> "
            "<code>ONLINE</code>\n"

            "📡 <b>API:</b> "
            "<code>CONFIGURED</code>\n"

            f"⏱ <b>Uptime:</b> "
            f"<code>{uptime // 3600}h "
            f"{(uptime % 3600) // 60}m "
            f"{uptime % 60}s</code>\n"

            f"👥 <b>Verified Users:</b> "
            f"<code>{len(VERIFIED_USERS)}</code>\n"

            f"🛠 <b>Available Tools:</b> "
            f"<code>{len(ACTIONS)}</code>"
        )

        await safe_send(
            update.message.reply_text,
            status_text,
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HELP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action == "help":

        context.user_data.pop(
            "mode",
            None
        )

        context.user_data.pop(
            "admin_mode",
            None
        )

        help_text = (
            "╔════════════════════════╗\n"
            "      🆘 <b>PREMIUM HELP</b>\n"
            "╚════════════════════════╝\n\n"

            "💎 <b>TRX EDITION SERVICES</b>\n\n"

            "🔍 Number Search\n"
            "🆔 Aadhar Info\n"
            "👤 Telegram Info\n"
            "📸 Instagram Info\n"
            "🚗 Vehicle RC\n"
            "🌐 IP Lookup\n"
            "🌦️ Weather\n"
            "📱 IMEI Info\n"
            "📮 Pincode Info\n"
            "🏦 IFSC Info\n"
            "🌍 Country Info\n"
            "💳 UPI Info\n"
            "💰 Paytm Info\n\n"

            "━━━━━━━━━━━━━━━━━━━━\n"
            "👇 Use the buttons below\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

        await safe_send(
            update.message.reply_text,
            help_text,
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NORMAL ACTION BUTTON
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if action in ACTIONS:

        _, _, prompt, _ = ACTIONS[action]

        context.user_data.pop(
            "admin_mode",
            None
        )

        context.user_data[
            "mode"
        ] = action

        await safe_send(
            update.message.reply_text,
            prompt,
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # COMMAND-LIKE / SAVED MODE INPUT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    mode = context.user_data.get(
        "mode"
    )

    if not mode:

        parts = text.split(
            maxsplit=1
        )

        if (
            len(parts) == 2
            and parts[0].lower() in ACTIONS
        ):

            mode = parts[0].lower()

            text_input = parts[1].strip()

            context.user_data.pop(
                "mode",
                None
            )

        else:

            return

    else:

        text_input = text

        context.user_data.pop(
            "mode",
            None
        )

    if mode not in ACTIONS:
        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # INPUT VALIDATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if not text_input:

        await update.message.reply_text(
            "❌ <b>Invalid input.</b>\n\n"
            "Please enter a valid value.",
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    if len(text_input) > 200:

        await update.message.reply_text(
            "❌ <b>Input too long.</b>\n\n"
            "Please enter a shorter value.",
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CHANNEL VERIFICATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if not is_admin(user_id):

        try:

            member_ok = await is_member(
                context.bot,
                user_id
            )

        except Exception:

            logger.exception(
                "Channel verification failed "
                "for user %s",
                user_id
            )

            member_ok = False

        if not member_ok:

            await update.message.reply_text(
                "❌ <b>Channel verification required.</b>\n\n"
                "Please join the channel first.",
                parse_mode="HTML",
                reply_markup=join_kb()
            )

            return

        VERIFIED_USERS.add(
            user_id
        )

        db_verify_user(
            user_id
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PREPARE API REQUEST
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    api_action, param_key, _, transform = ACTIONS[
        mode
    ]

    try:

        value = transform(
            text_input
        )

        if value is None:

            raise ValueError(
                "Transform returned None"
            )

        value = str(
            value
        ).strip()

    except Exception:

        logger.exception(
            "Input transform failed for action %s",
            mode
        )

        await update.message.reply_text(
            "❌ <b>Invalid input.</b>\n\n"
            "Please check your input and try again.",
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    if not value:

        await update.message.reply_text(
            "❌ <b>Invalid input.</b>\n\n"
            "Please enter a valid value.",
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    if is_protected_value(value):
        await update.message.reply_text(
            PROTECTION_MESSAGE,
            parse_mode="HTML",
            reply_markup=back_kb()
        )
        return

    if len(value) > 200:

        await update.message.reply_text(
            "❌ <b>Input too long.</b>\n\n"
            "Please enter a shorter value.",
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # RATE LIMIT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    now = time.time()

    last_request = LAST_REQUEST.get(
        user_id,
        0
    )

    elapsed = now - last_request

    remaining = (
        REQUEST_COOLDOWN - elapsed
    )

    if remaining > 0:

        wait_time = max(
            1,
            int(remaining + 0.999)
        )

        await update.message.reply_text(
            "⏳ <b>PLEASE WAIT</b>\n\n"
            f"আরও <b>{wait_time} sec</b> অপেক্ষা করো।\n"
            "তারপর আবার request পাঠাতে পারবে।",
            parse_mode="HTML",
            reply_markup=back_kb()
        )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CREDIT CHECK / DEDUCTION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    cost = BILLABLE_SAFE_ACTIONS.get(
        mode,
        0
    )

    if cost > 0:

        spent = spend_credits(
            user_id,
            cost,
            note=f"{mode} service"
        )

        if not spent:

            await update.message.reply_text(
                "❌ <b>INSUFFICIENT CREDITS</b>\n\n"
                "💳 তোমার পর্যাপ্ত credit নেই।\n"
                "⭐ Plans থেকে একটি plan নিতে পারো।",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

            return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PROCESSING MESSAGE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    try:

        wait = await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "      ⚡ <b>PROCESSING</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"

            f"🎯 <b>Service:</b> "
            f"<code>{html.escape(mode.upper())}</code>\n\n"

            "⏳ Please wait...",
            parse_mode="HTML"
        )

    except Exception:

        logger.exception(
            "Could not send processing message "
            "for %s",
            mode
        )

        if cost > 0:

            refund_credits(
                user_id,
                cost,
                note=(
                    f"{mode} processing "
                    "message failed"
                )
            )

        return

    # Cooldown starts after processing message.
    LAST_REQUEST[user_id] = time.time()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # REQUEST COUNT + LOG
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    db_increment_requests()

    # Actual lookup value is never logged.
    add_log(
        user_id,
        f"{mode} request"
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # API REQUEST
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    try:

        result = await asyncio.to_thread(
            call_api,
            api_action,
            {
                param_key: value
            }
        )

    except Exception:

        logger.exception(
            "Unexpected API call error for %s",
            mode
        )

        result = None

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # API ERROR → REFUND
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if result is None:

        if cost > 0:

            refund_credits(
                user_id,
                cost,
                note=f"{mode} API failed"
            )

        await safe_send(
            wait.edit_text,
            "╔════════════════════════╗\n"
            "       ❌ <b>API ERROR</b>\n"
            "╚════════════════════════╝\n\n"

            "⚠️ API is currently unavailable.\n"
            "💳 Your credit has been refunded.\n"
            "Please try again later.",
            parse_mode="HTML"
        )

        try:

            await wait.reply_text(
                "👇 Back to main menu:",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

        except Exception:

            logger.exception(
                "Could not send API error "
                "navigation for %s",
                mode
            )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # API FAILED → REFUND
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if (
        isinstance(result, dict)
        and result.get("status") is False
    ):

        if cost > 0:

            refund_credits(
                user_id,
                cost,
                note=(
                    f"{mode} failed "
                    "request refund"
                )
            )

        msg = html.escape(
            str(
                result.get(
                    "message",
                    "Unknown error"
                )
            )
        )

        refund_text = ""

        if cost > 0:

            refund_text = (
                "\n\n"
                "💳 Your credit has been refunded."
            )

        await safe_send(
            wait.edit_text,
            "╔════════════════════════╗\n"
            "       ❌ <b>REQUEST FAILED</b>\n"
            "╚════════════════════════╝\n\n"

            "⚠️ <b>API Message:</b>\n"
            f"<code>{msg}</code>"
            f"{refund_text}",
            parse_mode="HTML"
        )

        try:

            await wait.reply_text(
                "👇 Back to main menu:",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

        except Exception:

            logger.exception(
                "Could not send failed-request "
                "navigation for %s",
                mode
            )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FORMAT RESULT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    try:

        cleaned = clean_result(
            result
        )

        pretty = fmt(
            cleaned
        )

        output = (
            "╔════════════════════════╗\n"
            f"   💎 <b>"
            f"{html.escape(mode.upper())}"
            f" RESULT</b>\n"
            "╚════════════════════════╝\n\n"

            f"{pretty}\n\n"

            "━━━━━━━━━━━━━━━━━━━━\n"
            "💎 <i>TRX EDITION PREMIUM</i>\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

        output = smart_truncate(
            output,
            limit=4000
        )

    except Exception:

        logger.exception(
            "Result formatting failed for %s",
            mode
        )

        if cost > 0:

            refund_credits(
                user_id,
                cost,
                note=(
                    f"{mode} formatting "
                    "error refund"
                )
            )

        refund_text = ""

        if cost > 0:

            refund_text = (
                "\n\n"
                "💳 Your credit has been refunded."
            )

        await safe_send(
            wait.edit_text,
            "❌ <b>Could not format "
            "the API response.</b>"
            f"{refund_text}",
            parse_mode="HTML"
        )

        try:

            await wait.reply_text(
                "👇 Back to main menu:",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

        except Exception:

            logger.exception(
                "Could not send formatting-error "
                "navigation for %s",
                mode
            )

        return

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SHOW RESULT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    await safe_send(
        wait.edit_text,
        output,
        parse_mode="HTML"
    )

    try:

        await wait.reply_text(
            "👇 Back to main menu:",
            parse_mode="HTML",
            reply_markup=back_kb()
        )

    except Exception:

        logger.exception(
            "Could not send result navigation "
            "for %s",
            mode
        )

# ══════════════ COMMAND HANDLERS ══════════════


def make_cmd(action_id):
    api_action, param_key, prompt, transform = ACTIONS[action_id]

    async def cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return

        user_id = update.effective_user.id

        USER_IDS.add(user_id)
        db_add_user(user_id)

        # =====================================================
        # BAN CHECK
        # =====================================================
        if user_id in BANNED_USERS and not is_admin(user_id):
            context.user_data.pop("mode", None)

            await update.message.reply_text(
                "🚫 <b>You are banned from using this bot.</b>\n\n"
                "You cannot use any bot services.",
                parse_mode="HTML"
            )
            return

        # =====================================================
        # MAINTENANCE CHECK
        # =====================================================
        if MAINTENANCE_MODE and not is_admin(user_id):
            context.user_data.pop("mode", None)

            await update.message.reply_text(
                "🛠️ <b>BOT UNDER MAINTENANCE</b>\n\n"
                "Please try again later.",
                parse_mode="HTML"
            )
            return

        # =====================================================
        # CHANNEL JOIN CHECK
        # =====================================================
        if not is_admin(user_id):
            if not await is_member(context.bot, user_id):
                context.user_data.pop("mode", None)

                await update.message.reply_text(
                    "❌ <b>Please join our channel first.</b>\n\n"
                    "Join the channel and try again.",
                    parse_mode="HTML",
                    reply_markup=join_kb()
                )
                return

        # =====================================================
        # INPUT CHECK
        # =====================================================
        if not context.args:
            context.user_data["mode"] = action_id

            await safe_send(
                update.message.reply_text,
                prompt,
                parse_mode="HTML",
                reply_markup=back_kb()
            )
            return

        # =====================================================
        # INPUT TRANSFORM
        # =====================================================
        raw_input = " ".join(context.args).strip()

        if not raw_input:
            await update.message.reply_text(
                "❌ <b>Invalid input.</b>\n\n"
                "Please enter a valid value.",
                parse_mode="HTML",
                reply_markup=back_kb()
            )
            return

        # Basic input-size protection
        if len(raw_input) > 200:
            await update.message.reply_text(
                "❌ <b>Input too long.</b>\n\n"
                "Please enter a shorter value.",
                parse_mode="HTML",
                reply_markup=back_kb()
            )
            return

        try:
            value = transform(raw_input)

        except Exception:
            logger.exception(
                "Input transform failed for %s",
                action_id
            )

            await update.message.reply_text(
                "❌ <b>Invalid input.</b>\n\n"
                "Please check your input and try again.",
                parse_mode="HTML",
                reply_markup=back_kb()
            )
            return

        if not value:
            await update.message.reply_text(
                "❌ <b>Invalid input.</b>\n\n"
                "Please enter a valid value.",
                parse_mode="HTML",
                reply_markup=back_kb()
            )
            return

        if is_protected_value(value):
            await update.message.reply_text(PROTECTION_MESSAGE, parse_mode="HTML", reply_markup=back_kb())
            return

        # =====================================================
        # FINAL INPUT SIZE CHECK
        # =====================================================
        if len(value) > 200:
            await update.message.reply_text(
                "❌ <b>Input too long.</b>\n\n"
                "Please enter a shorter value.",
                parse_mode="HTML",
                reply_markup=back_kb()
            )
            return

        # =====================================================
        # CLEAR SAVED MODE
        # =====================================================
        context.user_data.pop("mode", None)

        # =====================================================
        # RATE LIMIT CHECK
        # =====================================================
        now = time.time()
        last = LAST_REQUEST.get(user_id, 0)

        remaining = REQUEST_COOLDOWN - (now - last)

        if remaining > 0:
            await update.message.reply_text(
                "⏳ <b>Please wait</b>\n\n"
                f"Try again after <b>{remaining:.1f}s</b>.",
                parse_mode="HTML",
                reply_markup=back_kb()
            )
            return

        # =====================================================
        # CREDIT COST
        # =====================================================
        cost = BILLABLE_SAFE_ACTIONS.get(
            action_id,
            0
        )

        # =====================================================
        # CREDIT DEDUCTION
        # =====================================================
        if cost > 0:
            spent = spend_credits(
                user_id,
                cost,
                note=f"{action_id} service"
            )

            if not spent:
                await update.message.reply_text(
                    "❌ <b>INSUFFICIENT CREDITS</b>\n\n"
                    f"💳 Required: <b>{cost}</b> credit\n\n"
                    "⭐ Please purchase a plan or wait "
                    "for your daily credits.",
                    parse_mode="HTML",
                    reply_markup=back_kb()
                )
                return

        # =====================================================
        # COOLDOWN SET
        # =====================================================
        LAST_REQUEST[user_id] = time.time()

        # =====================================================
        # REQUEST COUNT + LOG
        # =====================================================
        db_increment_requests()

        add_log(
            user_id,
            f"{action_id} request"
        )

        # =====================================================
        # PROCESSING MESSAGE
        # =====================================================
        processing = await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            "      ⚡ <b>PROCESSING</b>\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
            "⏳ Please wait...",
            parse_mode="HTML"
        )

        # =====================================================
        # API CALL
        # =====================================================
        try:
            result = await asyncio.to_thread(
                call_api,
                api_action,
                {param_key: value}
            )

        except Exception:
            logger.exception(
                "Unexpected API call error for %s",
                action_id
            )

            result = None

        # =====================================================
        # API ERROR → REFUND
        # =====================================================
        if result is None:

            if cost > 0:
                refund_credits(
                    user_id,
                    cost,
                    note=f"{action_id} API error refund"
                )

            await safe_send(
                processing.edit_text,
                "╔════════════════════════╗\n"
                "       ❌ <b>API ERROR</b>\n"
                "╚════════════════════════╝\n\n"
                "⚠️ No valid response received.\n\n"
                "💳 Your credit has been refunded.",
                parse_mode="HTML"
            )

            await processing.reply_text(
                "👇 Back to main menu:",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

            return

        # =====================================================
        # API STATUS FALSE → REFUND
        # =====================================================
        if (
            isinstance(result, dict)
            and result.get("status") is False
        ):

            if cost > 0:
                refund_credits(
                    user_id,
                    cost,
                    note=f"{action_id} failed request refund"
                )

            api_message = html.escape(
                str(
                    result.get(
                        "message",
                        "The API could not process your request."
                    )
                )
            )

            refund_text = ""

            if cost > 0:
                refund_text = (
                    "\n\n"
                    "💳 Your credit has been refunded."
                )

            await safe_send(
                processing.edit_text,
                "╔════════════════════════╗\n"
                "       ❌ <b>REQUEST FAILED</b>\n"
                "╚════════════════════════╝\n\n"
                f"⚠️ <b>API Message:</b>\n"
                f"<code>{api_message}</code>"
                f"{refund_text}",
                parse_mode="HTML"
            )

            await processing.reply_text(
                "👇 Back to main menu:",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

            return

        # =====================================================
        # FORMAT RESULT
        # =====================================================
        try:
            cleaned = clean_result(result)

            pretty = fmt(cleaned)

            output = (
                "╔══════════════════════════╗\n"
                "       ✅ <b>RESULT</b>\n"
                "╚══════════════════════════╝\n\n"
                f"{pretty}\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💎 <i>TRX EDITION PREMIUM</i>\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

            output = smart_truncate(output)

        except Exception:
            logger.exception(
                "Result formatting failed for %s",
                action_id
            )

            if cost > 0:
                refund_credits(
                    user_id,
                    cost,
                    note=f"{action_id} formatting error refund"
                )

            await safe_send(
                processing.edit_text,
                "❌ <b>Could not format the API response.</b>\n\n"
                "💳 Your credit has been refunded.",
                parse_mode="HTML"
            )

            await processing.reply_text(
                "👇 Back to main menu:",
                parse_mode="HTML",
                reply_markup=back_kb()
            )

            return

        # =====================================================
        # FINAL RESULT
        # =====================================================
        await safe_send(
            processing.edit_text,
            output,
            parse_mode="HTML"
        )

        await processing.reply_text(
            "👇 Back to main menu:",
            parse_mode="HTML",
            reply_markup=back_kb()
        )

    return cmd

# ══════════════ ERROR HANDLER ══════════════
async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    error = context.error

    logger.error(
        "Unhandled bot error: %r",
        error,
        exc_info=error
    )

    try:

        error_text = html.escape(
            str(error)
        )

        if len(error_text) > 2500:
            error_text = (
                error_text[:2500]
                + "..."
            )

        alert = (
            "🚨 <b>BOT ERROR ALERT</b>\n\n"
            "⚠️ An unexpected error occurred.\n\n"
            "🧩 <b>Error:</b>\n"
            f"<code>{error_text}</code>\n\n"
            f"🕐 <code>{datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S')}</code>"
        )

        for admin_id in ADMIN_IDS:

            try:

                await context.bot.send_message(
                    chat_id=admin_id,
                    text=alert,
                    parse_mode="HTML"
                )

            except Exception:
                logger.exception(
                    "Could not send error alert to admin %s",
                    admin_id
                )

    except Exception:
        logger.exception(
            "Error notification system failed"
        )


# ══════════════ MAIN ══════════════
def main():
    # ─────────────────────────────
    # 1️⃣ Database initialize
    # ─────────────────────────────
    init_db()

    # ─────────────────────────────
    # 2️⃣ Load saved database state
    # ─────────────────────────────
    load_db_state()

    # ─────────────────────────────
    # 3️⃣ Create Telegram application
    # ─────────────────────────────
    app = (
      Application.builder()
      .token(BOT_TOKEN)
      .post_init(post_init)
      .build()
    )

    # ─────────────────────────────
    # 4️⃣ Global error handler
    # ─────────────────────────────
    app.add_error_handler(error_handler)

    # ─────────────────────────────
    # 5️⃣ Group membership tracking
    # ─────────────────────────────
    app.add_handler(
        ChatMemberHandler(
            group_membership_update,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    # ─────────────────────────────
    # 6️⃣ Basic commands
    # ─────────────────────────────
    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("menu", menu_cmd)
    )
    
    app.add_handler(
        CommandHandler("wallet", wallet_cmd)
    )

    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("referral", referral_cmd))

    app.add_handler(
        CommandHandler("admin", admin_cmd)
    )

    app.add_handler(
        CommandHandler(
            "approve_payment",
            approve_payment_cmd
        )
    )
    
    app.add_handler(
        CommandHandler(
            "addplan",
            addplan_cmd
        )
    )
    

    # ─────────────────────────────
    # 6️⃣ API/action commands
    # ─────────────────────────────
    for aid in ACTIONS:
        app.add_handler(
            CommandHandler(
                aid,
                make_cmd(aid)
            )
        )

    # ─────────────────────────────
    # 7️⃣ Channel verification button
    # ─────────────────────────────
    app.add_handler(
        CallbackQueryHandler(
            check_join,
            pattern=r"^check_join$"
        )
    )

    # ─────────────────────────────
    # 8️⃣ Main menu button
    # ─────────────────────────────
    app.add_handler(
        CallbackQueryHandler(
            main_menu,
            pattern=r"^main_menu$"
        )
    )

    # ─────────────────────────────
    # 9️⃣ All other inline buttons
    # ─────────────────────────────
    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    # ─────────────────────────────
    # 🔟 Normal text messages
    # ─────────────────────────────
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_router
        )
    )

    # ─────────────────────────────
    # 🌐 START RENDER / FLASK HEALTH SERVER
    # ─────────────────────────────
    # Must listen on 0.0.0.0 and Render's assigned PORT.
    start_web_server()

    # ─────────────────────────────
    # 🚀 START BOT
    # ─────────────────────────────
    print("╔══════════════════════════════════╗")
    print("║   💎 TRX EDITION PREMIUM BOT 💎   ║")
    print("║   Status: RUNNING...              ║")
    print("╚══════════════════════════════════╝")

    try:
        app.run_polling(
            drop_pending_updates=True
        )

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")

    except Exception:
        logger.exception(
            "Fatal error while running bot"
        )


# ══════════════ ENTRY POINT ══════════════
if __name__ == "__main__":
    main()
