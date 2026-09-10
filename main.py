#!/usr/bin/env python3
"""
🚀 ZERO TRACE - Professional Python Bot Hosting Panel
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Features:
  ✅ Upload .py files → Instant bot live
  ✅ Start / Stop / Restart any hosted bot
  ✅ Real-time logs viewer (last 50 lines)
  ✅ Auto-restart crashed bots
  ✅ System resource monitor (CPU/RAM/Disk)
  ✅ Multi-admin support
  ✅ Beautiful inline button UI
  ✅ Process health checker
  ✅ File manager (list/delete files)
  ✅ Flask keep-alive for Render
  ✅ Auto-cleanup old logs
  ✅ Hosted bot environment variables support
  🛡️ Strict Security Gatekeeper (Admin-Only, Silent in Groups)
"""

import os
import sys
import signal
import subprocess
import threading
import time
import shutil
import logging
import asyncio
import html
import psutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter, BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    TypeHandler,
    filters,
    ApplicationHandlerStop,  # Strict security halt
)

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== ⚙️ CONFIG ==================
BOT_TOKEN = "8953914316:AAGp1wEPsiIibJ0JgQpmvaefMD9ayzDkF30"        # <-- Apna bot token daalo
ADMIN_IDS = [5453397878]      # <-- Apni admin telegram IDs daalo
BOT_NAME = "Backup hosting"
BOT_VERSION = "2.1"

# Directories
BOTS_DIR = Path("hosted_bots")
LOGS_DIR = Path("bot_logs")
ENV_DIR = Path("bot_envs")
BOTS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
ENV_DIR.mkdir(exist_ok=True)

# Timezone
IST = timezone(timedelta(hours=5, minutes=30))

# ================== 🎨 BANNERS ==================
BANNER = """╔══════════════════════════════════╗
║  🚀 ZERO TRACE HOSTING PANEL 🚀 ║
║       Professional Bot Host       ║
╚══════════════════════════════════╝"""

BANNER_MINI = """┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🚀 ZERO TRACE HOST 🚀  ┃
┃    Professional Panel     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━┛"""

# ================== 🔧 PROCESS MANAGER ==================
class ProcessManager:
    """Manages all hosted bot processes"""
    
    def __init__(self):
        self.processes = {}       # {filename: subprocess.Popen}
        self.start_times = {}     # {filename: datetime}
        self.restart_counts = {}  # {filename: int}
        self.auto_restart = {}    # {filename: bool}
        self.env_vars = {}        # {filename: dict}
    
    def start_bot(self, filename):
        """Start a bot process"""
        file_path = BOTS_DIR / filename
        if not file_path.exists():
            return False, f"❌ File `{filename}` not found!"
        
        # Kill existing if running
        if filename in self.processes:
            self.stop_bot(filename)
        
        # Prepare log file
        log_path = LOGS_DIR / f"{filename}.log"
        log_file = open(log_path, "w")
        
        # Prepare environment
        env = os.environ.copy()
        if filename in self.env_vars:
            env.update(self.env_vars[filename])
        
        try:
            process = subprocess.Popen(
                [sys.executable, str(file_path)],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=str(BOTS_DIR),
            )
            self.processes[filename] = process
            self.start_times[filename] = datetime.now(IST)
            self.restart_counts[filename] = self.restart_counts.get(filename, 0)
            if filename not in self.auto_restart:
                self.auto_restart[filename] = True
            
            return True, f"✅ `{filename}` started! PID: `{process.pid}`"
        except Exception as e:
            return False, f"❌ Failed to start: `{str(e)}`"
    
    def stop_bot(self, filename):
        """Stop a bot process"""
        if filename not in self.processes:
            return False, f"❌ `{filename}` is not running!"
        
        proc = self.processes[filename]
        try:
            # Try graceful shutdown first
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        except Exception:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except Exception:
                pass
        
        del self.processes[filename]
        if filename in self.start_times:
            del self.start_times[filename]
        
        return True, f"🛑 `{filename}` stopped successfully!"
    
    def restart_bot(self, filename):
        """Restart a bot"""
        self.stop_bot(filename)
        time.sleep(1)
        self.restart_counts[filename] = self.restart_counts.get(filename, 0) + 1
        return self.start_bot(filename)
    
    def get_status(self, filename):
        """Get status of a specific bot"""
        if filename not in self.processes:
            return "🔴 STOPPED"
        
        proc = self.processes[filename]
        if proc.poll() is None:
            return "🟢 RUNNING"
        else:
            return "💀 CRASHED"
    
    def get_all_status(self):
        """Get status of all bots"""
        all_files = list(BOTS_DIR.glob("*.py"))
        result = []
        for f in all_files:
            name = f.name
            status = self.get_status(name)
            pid = ""
            uptime = ""
            if name in self.processes and self.processes[name].poll() is None:
                pid = f"PID: {self.processes[name].pid}"
                if name in self.start_times:
                    delta = datetime.now(IST) - self.start_times[name]
                    hours, remainder = divmod(int(delta.total_seconds()), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime = f"⏱️ {hours}h {minutes}m {seconds}s"
            result.append({
                "name": name,
                "status": status,
                "pid": pid,
                "uptime": uptime,
                "auto_restart": self.auto_restart.get(name, True),
                "restarts": self.restart_counts.get(name, 0),
            })
        return result
    
    def get_logs(self, filename, lines=50):
        """Get last N lines of logs"""
        log_path = LOGS_DIR / f"{filename}.log"
        if not log_path.exists():
            return "📭 No logs found."
        
        try:
            with open(log_path, "r", errors="ignore") as f:
                all_lines = f.readlines()
                last_lines = all_lines[-lines:]
                return "".join(last_lines) if last_lines else "📭 Log file is empty."
        except Exception as e:
            return f"❌ Error reading logs: {str(e)}"
    
    def clear_logs(self, filename):
        """Clear log file"""
        log_path = LOGS_DIR / f"{filename}.log"
        try:
            open(log_path, "w").close()
            return True
        except Exception:
            return False
    
    def delete_bot(self, filename):
        """Delete bot file and its logs"""
        self.stop_bot(filename)
        
        file_path = BOTS_DIR / filename
        log_path = LOGS_DIR / f"{filename}.log"
        env_path = ENV_DIR / f"{filename}.env"
        
        for p in [file_path, log_path, env_path]:
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        
        for d in [self.processes, self.start_times, self.restart_counts, 
                  self.auto_restart, self.env_vars]:
            d.pop(filename, None)
        
        return True
    
    def get_file_size(self, filename):
        """Get file size in KB"""
        file_path = BOTS_DIR / filename
        if file_path.exists():
            size = file_path.stat().st_size
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size/1024:.1f} KB"
            else:
                return f"{size/(1024*1024):.1f} MB"
        return "N/A"


# Global process manager
PM = ProcessManager()


# ================== 🔄 AUTO-RESTART DAEMON ==================
def auto_restart_daemon():
    """Background thread that auto-restarts crashed bots"""
    while True:
        try:
            for filename in list(PM.processes.keys()):
                proc = PM.processes.get(filename)
                if proc and proc.poll() is not None:
                    # Process has died
                    if PM.auto_restart.get(filename, True):
                        logger.info(f"🔄 Auto-restarting crashed bot: {filename}")
                        PM.restart_counts[filename] = PM.restart_counts.get(filename, 0) + 1
                        
                        # Don't restart if crashed too many times
                        if PM.restart_counts[filename] > 10:
                            logger.warning(f"⚠️ {filename} crashed 10+ times. Disabling auto-restart.")
                            PM.auto_restart[filename] = False
                            del PM.processes[filename]
                            continue
                        
                        PM.start_bot(filename)
        except Exception as e:
            logger.error(f"Auto-restart daemon error: {e}")
        
        time.sleep(15)  # Check every 15 seconds


# ================== 🌐 FLASK KEEP-ALIVE ==================
web_app = Flask(__name__)

@web_app.route("/")
def index():
    running = sum(1 for p in PM.processes.values() if p.poll() is None)
    total = len(list(BOTS_DIR.glob("*.py")))
    return f"""
    <html>
    <head><title>{BOT_NAME}</title></head>
    <body style="background:#1a1a2e;color:#eee;font-family:monospace;padding:40px;text-align:center;">
        <h1>🚀 {BOT_NAME}</h1>
        <p>Version: {BOT_VERSION}</p>
        <hr style="border-color:#333">
        <p>🟢 Running Bots: <b>{running}</b></p>
        <p>📁 Total Files: <b>{total}</b></p>
        <p>💚 Server Status: <b>ONLINE</b></p>
        <p style="color:#555">Last checked: {datetime.now(IST).strftime('%d-%m-%Y %H:%M:%S IST')}</p>
    </body>
    </html>
    """

def start_webserver():
    import logging as lg
    lg.getLogger("werkzeug").setLevel(lg.ERROR)
    web_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))


# ================== 🛡️ HELPERS ==================
def is_admin(uid):
    return int(uid) in ADMIN_IDS

def safe_name(user):
    return html.escape(user.first_name or "User")

def get_system_info():
    """Get system resource info"""
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    return {
        "cpu_percent": cpu,
        "ram_used": f"{mem.used / (1024**2):.0f}",
        "ram_total": f"{mem.total / (1024**2):.0f}",
        "ram_percent": mem.percent,
        "disk_used": f"{disk.used / (1024**3):.1f}",
        "disk_total": f"{disk.total / (1024**3):.1f}",
        "disk_percent": disk.percent,
    }

def now_ist():
    return datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")


# ================== 🛡️ SAFE SENDERS ==================
async def safe_reply(update, text, reply_markup=None):
    msg = update.effective_message
    if not msg:
        return None
    try:
        return await msg.reply_text(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after + 0.5)
        try:
            return await msg.reply_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
        except Exception:
            return None
    except Exception:
        try:
            clean = text.replace("<b>", "").replace("</b>", "")
            clean = clean.replace("<code>", "").replace("</code>", "")
            clean = clean.replace("<i>", "").replace("</i>", "")
            return await msg.reply_text(clean[:4096], reply_markup=reply_markup)
        except Exception:
            return None


async def safe_edit(target, text, reply_markup=None):
    if not target:
        return None
    try:
        if hasattr(target, "edit_message_text"):
            return await target.edit_message_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
        elif hasattr(target, "edit_text"):
            return await target.edit_text(
                text, reply_markup=reply_markup, parse_mode="HTML"
            )
    except BadRequest as e:
        if "not modified" in str(e):
            return target
    except Exception:
        pass
    return None


# ================== 🎹 KEYBOARDS ==================
def main_menu_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="dashboard"),
            InlineKeyboardButton("📁 My Bots", callback_data="my_bots"),
        ],
        [
            InlineKeyboardButton("📥 Upload Bot", callback_data="upload_info"),
            InlineKeyboardButton("🖥️ System", callback_data="system_info"),
        ],
        [
            InlineKeyboardButton("▶️ Start All", callback_data="start_all"),
            InlineKeyboardButton("⏹️ Stop All", callback_data="stop_all"),
        ],
        [
            InlineKeyboardButton("🔄 Restart All", callback_data="restart_all"),
            InlineKeyboardButton("🗑️ File Manager", callback_data="file_manager"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
    ])


def bot_action_kb(filename):
    status = PM.get_status(filename)
    ar = PM.auto_restart.get(filename, True)
    ar_text = "🟢 Auto-Restart: ON" if ar else "🔴 Auto-Restart: OFF"
    
    buttons = []
    if "RUNNING" in status:
        buttons.append([
            InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{filename}"),
            InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{filename}"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton("▶️ Start", callback_data=f"start_{filename}"),
        ])
    
    buttons.extend([
        [
            InlineKeyboardButton("📋 Logs (Last 30)", callback_data=f"logs30_{filename}"),
            InlineKeyboardButton("📋 Logs (Last 100)", callback_data=f"logs100_{filename}"),
        ],
        [
            InlineKeyboardButton("🧹 Clear Logs", callback_data=f"clearlogs_{filename}"),
            InlineKeyboardButton(ar_text, callback_data=f"togglear_{filename}"),
        ],
        [
            InlineKeyboardButton("📤 Download File", callback_data=f"download_{filename}"),
            InlineKeyboardButton("🗑️ Delete Bot", callback_data=f"confirmdelete_{filename}"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=f"botinfo_{filename}"),
            InlineKeyboardButton("🔙 Back", callback_data="my_bots"),
        ],
    ])
    return InlineKeyboardMarkup(buttons)


def confirm_delete_kb(filename):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Yes, Delete!", callback_data=f"delete_{filename}"
            ),
            InlineKeyboardButton("❌ Cancel", callback_data=f"botinfo_{filename}"),
        ]
    ])


def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])


def settings_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔄 Restart Host Bot", callback_data="restart_host"
            ),
        ],
        [
            InlineKeyboardButton(
                "🧹 Clean All Logs", callback_data="clean_all_logs"
            ),
            InlineKeyboardButton(
                "📊 Process List", callback_data="process_list"
            ),
        ],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])


# ================== 🚀 HANDLERS ==================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    running = sum(
        1
        for p in PM.processes.values()
        if p.poll() is None
    )
    total = len(list(BOTS_DIR.glob("*.py")))
    sys_info = get_system_info()

    txt = (
        f"<code>{BANNER}</code>\n\n"
        f"👋 Welcome, <b>{safe_name(user)}</b>!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Quick Stats:</b>\n"
        f"  📁 Total Bots: <code>{total}</code>\n"
        f"  🟢 Running: <code>{running}</code>\n"
        f"  🔴 Stopped: <code>{total - running}</code>\n\n"
        f"🖥️ <b>Server:</b>\n"
        f"  💻 CPU: <code>{sys_info['cpu_percent']}%</code>\n"
        f"  🧠 RAM: <code>{sys_info['ram_used']}/{sys_info['ram_total']} MB"
        f" ({sys_info['ram_percent']}%)</code>\n\n"
        f"⏰ <code>{now_ist()} IST</code>\n\n"
        f"👇 <b>Select an option:</b>"
    )
    if update.callback_query:
        await safe_edit(update.callback_query, txt, main_menu_kb())
    else:
        await safe_reply(update, txt, main_menu_kb())


async def main_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)


# ================== 📊 DASHBOARD ==================
async def dashboard_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    all_status = PM.get_all_status()
    if not all_status:
        txt = (
            f"<code>{BANNER_MINI}</code>\n\n"
            f"📊 <b>DASHBOARD</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📭 No bots uploaded yet.\n\n"
            f"📥 Send a <code>.py</code> file to upload!"
        )
        await safe_edit(q, txt, back_kb())
        return

    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📊 <b>DASHBOARD</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    for bot in all_status:
        ar_icon = "🔄" if bot["auto_restart"] else "⏸️"
        size = PM.get_file_size(bot["name"])
        txt += (
            f"{bot['status']} <code>{html.escape(bot['name'])}</code>\n"
            f"   {bot['pid']}  {bot['uptime']}\n"
            f"   📦 {size}  {ar_icon} Restarts: {bot['restarts']}\n\n"
        )
    
    txt += f"⏰ <code>{now_ist()}</code>"
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="dashboard")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])
    await safe_edit(q, txt, kb)


# ================== 📁 MY BOTS ==================
async def my_bots_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    all_files = sorted(BOTS_DIR.glob("*.py"))
    if not all_files:
        await safe_edit(
            q,
            f"<code>{BANNER_MINI}</code>\n\n"
            f"📁 <b>MY BOTS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📭 No bots found.\n\n"
            f"📥 Send a <code>.py</code> file to get started!",
            back_kb(),
        )
        return

    buttons = []
    for f in all_files:
        name = f.name
        status = PM.get_status(name)
        icon = "🟢" if "RUNNING" in status else ("💀" if "CRASHED" in status else "🔴")
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{icon} {name}", callback_data=f"botinfo_{name}"
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    )

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📁 <b>MY BOTS ({len(all_files)})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 Tap on any bot to manage:",
        InlineKeyboardMarkup(buttons),
    )


# ================== 🤖 BOT INFO ==================
async def bot_info_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    filename = q.data.replace("botinfo_", "")
    status = PM.get_status(filename)
    size = PM.get_file_size(filename)
    ar = "🟢 ON" if PM.auto_restart.get(filename, True) else "🔴 OFF"
    restarts = PM.restart_counts.get(filename, 0)
    
    uptime_str = "N/A"
    pid_str = "N/A"
    if filename in PM.processes and PM.processes[filename].poll() is None:
        pid_str = str(PM.processes[filename].pid)
        if filename in PM.start_times:
            delta = datetime.now(IST) - PM.start_times[filename]
            h, rem = divmod(int(delta.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            uptime_str = f"{h}h {m}m {s}s"

    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🤖 <b>BOT DETAILS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 <b>File:</b> <code>{html.escape(filename)}</code>\n"
        f"📊 <b>Status:</b> {status}\n"
        f"🆔 <b>PID:</b> <code>{pid_str}</code>\n"
        f"⏱️ <b>Uptime:</b> <code>{uptime_str}</code>\n"
        f"📦 <b>Size:</b> <code>{size}</code>\n"
        f"🔄 <b>Auto-Restart:</b> {ar}\n"
        f"🔢 <b>Total Restarts:</b> <code>{restarts}</code>\n\n"
        f"⏰ <code>{now_ist()}</code>"
    )
    await safe_edit(q, txt, bot_action_kb(filename))


# ================== ▶️ START/STOP/RESTART SINGLE ==================
async def start_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Starting...")
    filename = q.data.replace("start_", "")
    ok, msg = PM.start_bot(filename)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n{msg}\n\n⏰ <code>{now_ist()}</code>",
        bot_action_kb(filename),
    )


async def stop_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Stopping...")
    filename = q.data.replace("stop_", "")
    ok, msg = PM.stop_bot(filename)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n{msg}\n\n⏰ <code>{now_ist()}</code>",
        bot_action_kb(filename),
    )


async def restart_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Restarting...")
    filename = q.data.replace("restart_", "")
    ok, msg = PM.restart_bot(filename)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n{msg}\n\n⏰ <code>{now_ist()}</code>",
        bot_action_kb(filename),
    )


# ================== 📋 LOGS VIEWER ==================
async def view_logs_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data.startswith("logs30_"):
        filename = data.replace("logs30_", "")
        lines = 30
    elif data.startswith("logs100_"):
        filename = data.replace("logs100_", "")
        lines = 100
    else:
        return

    logs = PM.get_logs(filename, lines)
    
    # Truncate if too long for telegram
    safe_logs = html.escape(logs)
    if len(safe_logs) > 3500:
        safe_logs = safe_logs[-3500:]
        safe_logs = "...(truncated)\n" + safe_logs

    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📋 <b>LOGS:</b> <code>{html.escape(filename)}</code>\n"
        f"📏 Last <b>{lines}</b> lines\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<pre>{safe_logs}</pre>"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=q.data),
            InlineKeyboardButton("🧹 Clear", callback_data=f"clearlogs_{filename}"),
        ],
        [InlineKeyboardButton("🔙 Bot Info", callback_data=f"botinfo_{filename}")],
    ])
    await safe_edit(q, txt, kb)


async def clear_logs_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Logs cleared!")
    filename = q.data.replace("clearlogs_", "")
    PM.clear_logs(filename)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🧹 Logs for <code>{html.escape(filename)}</code> cleared!",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Bot Info", callback_data=f"botinfo_{filename}")]
        ]),
    )


# ================== 🔄 AUTO-RESTART TOGGLE ==================
async def toggle_ar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    filename = q.data.replace("togglear_", "")
    current = PM.auto_restart.get(filename, True)
    PM.auto_restart[filename] = not current
    new_state = "ON 🟢" if PM.auto_restart[filename] else "OFF 🔴"

    await q.answer(f"Auto-Restart: {new_state}")
    # Refresh bot info page
    q.data = f"botinfo_{filename}"
    await bot_info_cb(update, context)


# ================== 🗑️ DELETE BOT ==================
async def confirm_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    filename = q.data.replace("confirmdelete_", "")
    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"⚠️ <b>CONFIRM DELETION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗑️ Are you sure you want to <b>permanently delete</b>:\n"
        f"📁 <code>{html.escape(filename)}</code>\n\n"
        f"⚠️ This will:\n"
        f"  • Stop the running bot\n"
        f"  • Delete the .py file\n"
        f"  • Delete all logs\n\n"
        f"❌ <b>This action CANNOT be undone!</b>",
        confirm_delete_kb(filename),
    )


async def delete_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Deleted!")
    filename = q.data.replace("delete_", "")
    PM.delete_bot(filename)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🗑️ <code>{html.escape(filename)}</code> <b>permanently deleted!</b>",
        back_kb(),
    )


# ================== 📤 DOWNLOAD BOT FILE ==================
async def download_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Sending file...")
    filename = q.data.replace("download_", "")
    file_path = BOTS_DIR / filename

    if file_path.exists():
        try:
            await context.bot.send_document(
                chat_id=q.from_user.id,
                document=open(file_path, "rb"),
                filename=filename,
                caption=f"📤 <b>Downloaded:</b> <code>{html.escape(filename)}</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            await safe_edit(
                q, f"❌ Failed to send file: {str(e)}", back_kb()
            )
    else:
        await safe_edit(q, "❌ File not found!", back_kb())


# ================== ▶️⏹️🔄 BULK ACTIONS ==================
async def start_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Starting all...")
    all_files = list(BOTS_DIR.glob("*.py"))
    started = 0
    failed = 0
    for f in all_files:
        ok, _ = PM.start_bot(f.name)
        if ok:
            started += 1
        else:
            failed += 1

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"▶️ <b>START ALL RESULTS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Started: <code>{started}</code>\n"
        f"❌ Failed: <code>{failed}</code>\n"
        f"📁 Total: <code>{len(all_files)}</code>",
        back_kb(),
    )


async def stop_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Stopping all...")
    stopped = 0
    for filename in list(PM.processes.keys()):
        ok, _ = PM.stop_bot(filename)
        if ok:
            stopped += 1

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"⏹️ <b>ALL BOTS STOPPED</b>\n\n"
        f"🛑 Stopped: <code>{stopped}</code> bots",
        back_kb(),
    )


async def restart_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Restarting all...")
    all_files = list(BOTS_DIR.glob("*.py"))
    restarted = 0
    for f in all_files:
        ok, _ = PM.restart_bot(f.name)
        if ok:
            restarted += 1

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🔄 <b>ALL BOTS RESTARTED</b>\n\n"
        f"✅ Restarted: <code>{restarted}</code> bots",
        back_kb(),
    )


# ================== 🖥️ SYSTEM INFO ==================
async def system_info_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    info = get_system_info()
    running = sum(1 for p in PM.processes.values() if p.poll() is None)
    
    # RAM bar
    ram_pct = info["ram_percent"]
    ram_filled = int(ram_pct / 5)
    ram_bar = "█" * ram_filled + "░" * (20 - ram_filled)
    
    # CPU bar
    cpu_pct = info["cpu_percent"]
    cpu_filled = int(cpu_pct / 5)
    cpu_bar = "█" * cpu_filled + "░" * (20 - cpu_filled)
    
    # Disk bar
    disk_pct = info["disk_percent"]
    disk_filled = int(disk_pct / 5)
    disk_bar = "█" * disk_filled + "░" * (20 - disk_filled)

    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🖥️ <b>SYSTEM RESOURCES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💻 <b>CPU Usage:</b>\n"
        f"   <code>[{cpu_bar}]</code> <b>{cpu_pct}%</b>\n\n"
        f"🧠 <b>RAM Usage:</b>\n"
        f"   <code>[{ram_bar}]</code> <b>{ram_pct}%</b>\n"
        f"   📊 {info['ram_used']} / {info['ram_total']} MB\n\n"
        f"💾 <b>Disk Usage:</b>\n"
        f"   <code>[{disk_bar}]</code> <b>{disk_pct}%</b>\n"
        f"   📊 {info['disk_used']} / {info['disk_total']} GB\n\n"
        f"🤖 <b>Running Bots:</b> <code>{running}</code>\n"
        f"🐍 <b>Python:</b> <code>{sys.version.split()[0]}</code>\n"
        f"💻 <b>Platform:</b> <code>{sys.platform}</code>\n\n"
        f"⏰ <code>{now_ist()}</code>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="system_info")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])
    await safe_edit(q, txt, kb)


# ================== 📥 UPLOAD INFO ==================
async def upload_info_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📥 <b>HOW TO UPLOAD A BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"1️⃣ Apni <code>.py</code> Python file ready rakho\n\n"
        f"2️⃣ Is chat me file <b>document</b> ke roop me bhejo\n"
        f"   (Photo ya media ke roop me NAHI, document jaisa)\n\n"
        f"3️⃣ Bot file ko automatically download karke\n"
        f"   turant <b>LIVE</b> kar dega! 🚀\n\n"
        f"⚠️ <b>Important Notes:</b>\n"
        f"  • Sirf <code>.py</code> files accept hogi\n"
        f"  • Agar same naam ki file pehle se hai toh\n"
        f"    purani file <b>replace</b> ho jayegi\n"
        f"  • File ka BOT_TOKEN correct hona chahiye\n"
        f"  • Required libraries server pe installed honi chahiye\n\n"
        f"📁 Bas file bhej do neeche! 👇",
        back_kb(),
    )


# ================== 📥 FILE UPLOAD HANDLER ==================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    if not doc.file_name or not doc.file_name.endswith(".py"):
        await safe_reply(
            update,
            "❌ <b>Invalid File!</b>\n\n"
            "Sirf <code>.py</code> (Python) files bhejo!",
        )
        return

    file_name = doc.file_name
    file_path = BOTS_DIR / file_name

    # Check file size (max 5 MB)
    if doc.file_size and doc.file_size > 5 * 1024 * 1024:
        await safe_reply(
            update,
            "❌ <b>File too large!</b>\n\n"
            "Maximum file size: <code>5 MB</code>",
        )
        return

    # Show downloading status
    status_msg = await safe_reply(
        update,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"⏳ <b>Downloading</b> <code>{html.escape(file_name)}</code>...\n\n"
        f"<code>[██████░░░░░░░░░░░░░░]</code> 30%",
    )

    # Was this bot already running? Stop it first
    was_running = file_name in PM.processes and PM.processes[file_name].poll() is None
    if was_running:
        PM.stop_bot(file_name)

    # Download file
    tg_file = await doc.get_file()
    await tg_file.download_to_drive(str(file_path))

    # Update progress
    await safe_edit(
        status_msg,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📥 <b>Downloaded!</b> Starting bot...\n\n"
        f"<code>[████████████████░░░░]</code> 80%",
    )

    # Start the bot
    await asyncio.sleep(0.5)
    ok, msg = PM.start_bot(file_name)

    if ok:
        # Verify it's actually running after 2 seconds
        await asyncio.sleep(2)
        status = PM.get_status(file_name)

        if "RUNNING" in status:
            final_text = (
                f"<code>{BANNER_MINI}</code>\n\n"
                f"✅ <b>BOT IS LIVE!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📁 <b>File:</b> <code>{html.escape(file_name)}</code>\n"
                f"📦 <b>Size:</b> <code>{PM.get_file_size(file_name)}</code>\n"
                f"🆔 <b>PID:</b> <code>{PM.processes[file_name].pid}</code>\n"
                f"🟢 <b>Status:</b> Running\n"
                f"🔄 <b>Auto-Restart:</b> ON\n\n"
                f"<code>[████████████████████]</code> 100% ✅\n\n"
                f"⏰ <code>{now_ist()}</code>"
            )
            if was_running:
                final_text = final_text.replace(
                    "BOT IS LIVE!", "BOT UPDATED & RESTARTED!"
                )
        else:
            # Bot crashed immediately
            logs = PM.get_logs(file_name, 20)
            safe_logs = html.escape(logs)[:1500]
            final_text = (
                f"<code>{BANNER_MINI}</code>\n\n"
                f"⚠️ <b>BOT CRASHED IMMEDIATELY!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📁 File: <code>{html.escape(file_name)}</code>\n"
                f"💀 Status: CRASHED after start\n\n"
                f"📋 <b>Error Logs:</b>\n"
                f"<pre>{safe_logs}</pre>"
            )
    else:
        final_text = (
            f"<code>{BANNER_MINI}</code>\n\n"
            f"❌ <b>FAILED TO START!</b>\n\n{msg}"
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🤖 Manage Bot", callback_data=f"botinfo_{file_name}"
        )],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])
    await safe_edit(status_msg, final_text, kb)


# ================== 🗑️ FILE MANAGER ==================
async def file_manager_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    all_files = sorted(BOTS_DIR.glob("*.py"))
    log_files = sorted(LOGS_DIR.glob("*.log"))

    total_size = sum(f.stat().st_size for f in all_files) / 1024
    log_size = sum(f.stat().st_size for f in log_files) / 1024

    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🗑️ <b>FILE MANAGER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 <b>Bot Files:</b> <code>{len(all_files)}</code> "
        f"({total_size:.1f} KB)\n"
        f"📋 <b>Log Files:</b> <code>{len(log_files)}</code> "
        f"({log_size:.1f} KB)\n\n"
    )

    for f in all_files:
        name = f.name
        size = PM.get_file_size(name)
        status = PM.get_status(name)
        icon = "🟢" if "RUNNING" in status else "🔴"
        txt += f"  {icon} <code>{html.escape(name)}</code> ({size})\n"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🧹 Delete ALL Logs", callback_data="clean_all_logs"
        )],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])
    await safe_edit(q, txt, kb)


# ================== ⚙️ SETTINGS ==================
async def settings_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    running = sum(1 for p in PM.processes.values() if p.poll() is None)
    ar_on = sum(1 for v in PM.auto_restart.values() if v)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"⚙️ <b>SETTINGS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Running:</b> <code>{running}</code>\n"
        f"🔄 <b>Auto-Restart Active:</b> <code>{ar_on}</code>\n"
        f"🐍 <b>Python:</b> <code>{sys.version.split()[0]}</code>\n"
        f"📂 <b>Bot Dir:</b> <code>{BOTS_DIR}</code>\n"
        f"📋 <b>Log Dir:</b> <code>{LOGS_DIR}</code>\n\n"
        f"👑 <b>Admins:</b> {', '.join(f'<code>{a}</code>' for a in ADMIN_IDS)}",
        settings_kb(),
    )


async def clean_all_logs_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("All logs cleaned!")
    count = 0
    for log_file in LOGS_DIR.glob("*.log"):
        try:
            open(log_file, "w").close()
            count += 1
        except Exception:
            pass

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🧹 <b>All Logs Cleaned!</b>\n\n"
        f"📋 Cleared: <code>{count}</code> log files",
        back_kb(),
    )


async def process_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📊 <b>ACTIVE PROCESSES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not PM.processes:
        txt += "📭 No processes running."
    else:
        for name, proc in PM.processes.items():
            alive = proc.poll() is None
            icon = "🟢" if alive else "💀"
            pid = proc.pid
            try:
                if alive:
                    p = psutil.Process(pid)
                    mem = p.memory_info().rss / (1024 * 1024)
                    cpu = p.cpu_percent()
                    txt += (
                        f"{icon} <code>{html.escape(name)}</code>\n"
                        f"   PID: <code>{pid}</code> | "
                        f"RAM: <code>{mem:.1f}MB</code> | "
                        f"CPU: <code>{cpu}%</code>\n\n"
                    )
                else:
                    txt += (
                        f"{icon} <code>{html.escape(name)}</code>\n"
                        f"   PID: <code>{pid}</code> | Status: DEAD\n\n"
                    )
            except Exception:
                txt += (
                    f"{icon} <code>{html.escape(name)}</code>\n"
                    f"   PID: <code>{pid}</code>\n\n"
                )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="process_list")],
        [InlineKeyboardButton("🔙 Settings", callback_data="settings")],
    ])
    await safe_edit(q, txt, kb)


# ================== ❓ HELP ==================
async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await safe_edit(
        q,
        f"<code>{BANNER}</code>\n\n"
        f"❓ <b>HELP & COMMANDS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📥 <b>Upload Bot:</b>\n"
        f"  Bas <code>.py</code> file send karo, bot live!\n\n"
        f"⚙️ <b>Manage Bot:</b>\n"
        f"  📁 My Bots → Bot choose → Actions\n\n"
        f"🔧 <b>Features:</b>\n"
        f"  ▶️ Start/Stop/Restart single bot\n"
        f"  ▶️ Start/Stop/Restart ALL bots\n"
        f"  📋 View logs (last 30 or 100 lines)\n"
        f"  🧹 Clear logs\n"
        f"  🔄 Auto-restart ON/OFF\n"
        f"  📤 Download file back\n"
        f"  🗑️ Delete bot permanently\n"
        f"  🖥️ System resources monitor\n"
        f"  📊 Per-process RAM/CPU usage\n\n"
        f"💡 <b>Tips:</b>\n"
        f"  • Same name ki file dobara bhejne pe\n"
        f"    purani file replace ho jayegi\n"
        f"  • Crashed bots auto-restart hote hain\n"
        f"  • 10+ baar crash = auto-restart band\n\n"
        f"🔧 <b>Version:</b> <code>{BOT_VERSION}</code>",
        back_kb(),
    )


# ================== 🛡️ STRICT SECURITY GATEKEEPER ==================
async def global_security_gatekeeper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Global Interceptor:
    Blocks unauthorized users instantly before any other handler is executed.
    Stays completely silent in Group Chats to prevent spamming.
    """
    user = update.effective_user
    chat = update.effective_chat
    
    # Ignore updates where no user context is involved (e.g., channel updates, polls)
    if not user:
        return

    # Check if user is an authorized admin
    if not is_admin(user.id):
        # 1. Silently ignore in group/supergroups/channels (No spam warning)
        if chat and chat.type in ["group", "supergroup", "channel"]:
            raise ApplicationHandlerStop()

        # 2. Private PM: Send strict access denied warning
        if update.message:
            await update.message.reply_text(
                "⛔ <b>ACCESS DENIED</b>\n\n"
                "🔒 This is a private bot hosting panel.\n"
                "Only authorized admins can access.",
                parse_mode="HTML"
            )
        elif update.callback_query:
            try:
                await update.callback_query.answer(
                    "⛔ ACCESS DENIED: Unauthorized Access Attempted!",
                    show_alert=True
                )
            except Exception:
                pass
        
        # Stop propagating further into commands, messages, or button callbacks
        raise ApplicationHandlerStop()


# ================== 🚨 ERROR HANDLER ==================
async def error_handler(update, context):
    if isinstance(context.error, RetryAfter):
        return
    logger.error(f"Error: {context.error}")


# ================== 🏁 MAIN ==================
def main():
    print(f"{'='*50}")
    print(f"  🚀 {BOT_NAME} v{BOT_VERSION}")
    print(f"  📂 Bot Dir: {BOTS_DIR}")
    print(f"  📋 Log Dir: {LOGS_DIR}")
    print(f"  👑 Admins: {ADMIN_IDS}")
    print(f"{'='*50}")

    # Clean webhook
    try:
        import requests
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}"
            f"/deleteWebhook?drop_pending_updates=false",
            timeout=15,
        )
    except Exception:
        pass

    # Start Flask keep-alive
    threading.Thread(target=start_webserver, daemon=True).start()
    print("🌐 Flask keep-alive server started!")

    # Start auto-restart daemon
    threading.Thread(target=auto_restart_daemon, daemon=True).start()
    print("🔄 Auto-restart daemon started!")

    # Build Telegram app
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ================== REGISTER HANDLERS ==================
    # 🚨 REGISTER GLOBAL SECURITY GATEKEEPER FIRST (Group -1 Interceptor)
    app.add_handler(TypeHandler(Update, global_security_gatekeeper), group=-1)

    # Command handlers
    app.add_handler(CommandHandler("start", start_cmd))

    # Callback handlers
    callbacks = {
        "main_menu": main_menu_cb,
        "dashboard": dashboard_cb,
        "my_bots": my_bots_cb,
        "upload_info": upload_info_cb,
        "system_info": system_info_cb,
        "start_all": start_all_cb,
        "stop_all": stop_all_cb,
        "restart_all": restart_all_cb,
        "file_manager": file_manager_cb,
        "settings": settings_cb,
        "clean_all_logs": clean_all_logs_cb,
        "process_list": process_list_cb,
        "help": help_cb,
    }
    for pattern, handler in callbacks.items():
        app.add_handler(CallbackQueryHandler(handler, pattern=f"^{pattern}$"))

    # Dynamic bot action callbacks
    app.add_handler(CallbackQueryHandler(bot_info_cb, pattern=r"^botinfo_"))
    app.add_handler(CallbackQueryHandler(start_bot_cb, pattern=r"^start_"))
    app.add_handler(CallbackQueryHandler(stop_bot_cb, pattern=r"^stop_"))
    app.add_handler(CallbackQueryHandler(restart_bot_cb, pattern=r"^restart_"))
    app.add_handler(CallbackQueryHandler(view_logs_cb, pattern=r"^logs(30|100)_"))
    app.add_handler(CallbackQueryHandler(clear_logs_cb, pattern=r"^clearlogs_"))
    app.add_handler(CallbackQueryHandler(toggle_ar_cb, pattern=r"^togglear_"))
    app.add_handler(CallbackQueryHandler(confirm_delete_cb, pattern=r"^confirmdelete_"))
    app.add_handler(CallbackQueryHandler(delete_bot_cb, pattern=r"^delete_"))
    app.add_handler(CallbackQueryHandler(download_bot_cb, pattern=r"^download_"))

    # Document upload handler
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Error handler
    app.add_error_handler(error_handler)

    print("🚀 Bot is ONLINE! Polling started...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
