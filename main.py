#!/usr/bin/env python3
"""
🚀 ZERO TRACE - Professional Python, JS & ZIP Bot Hosting Panel
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Features:
  ✅ Upload .py / .js / .zip files → Instant live deployment
  ✅ Auto-detects startup files inside ZIPs (Python & Node.js)
  ✅ Start / Stop / Restart any hosted project
  ✅ Real-time logs viewer (last 30/100 lines)
  ✅ Auto-restart crashed bots (daemon protection)
  ✅ System resource monitor (CPU/RAM/Disk)
  ✅ Multi-admin support (Strict PM security)
  ✅ Process health checker & file manager
  ✅ Flask keep-alive for Render 24/7 running
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
import zipfile
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
    ApplicationHandlerStop,
)

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== ⚙️ CONFIG ==================
BOT_TOKEN = "8984086840:AAFjnKIH_4L2stlPri0KXnkDYWAjy070Vew"        # <-- Apna bot token daalo
ADMIN_IDS = [5453397878]      # <-- Apni admin telegram IDs daalo
BOT_NAME = "MAKI CHUT"
BOT_VERSION = "2.2"

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
║   Python • Node.js • ZIP Deploy  ║
╚══════════════════════════════════╝"""

BANNER_MINI = """┏━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🚀 ZERO TRACE HOST 🚀  ┃
┃   Multi-Runtime Host   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━┛"""

# ================== 🔧 PROCESS MANAGER ==================
class ProcessManager:
    """Manages all hosted bot processes (Python, Node.js & ZIP Projects)"""
    
    def __init__(self):
        self.processes = {}       # {name: subprocess.Popen}
        self.start_times = {}     # {name: datetime}
        self.restart_counts = {}  # {name: int}
        self.auto_restart = {}    # {name: bool}
        self.env_vars = {}        # {name: dict}
        self.run_commands = {}    # {name: list of args}
        self.working_dirs = {}    # {name: Path}
    
    def detect_run_config(self, name):
        """Auto-detects executable and path configurations based on file/folder type"""
        target_path = BOTS_DIR / name
        if not target_path.exists():
            return None, None, "❌ Target not found!"
            
        # Case 1: Directory (Extracted ZIP)
        if target_path.is_dir():
            # Priority order of startup files
            detect_patterns = [
                ("main.py", [sys.executable, "main.py"]),
                ("bot.py", [sys.executable, "bot.py"]),
                ("index.js", ["node", "index.js"]),
                ("app.js", ["node", "app.js"]),
                ("server.js", ["node", "server.js"]),
                ("main.js", ["node", "main.js"])
            ]
            for file_pattern, cmd in detect_patterns:
                if (target_path / file_pattern).exists():
                    return cmd, target_path, "success"
            return None, None, f"❌ ZIP me koi standard startup file (`main.py`, `bot.py`, `index.js`, `app.js`) nahi mili!"
            
        # Case 2: Single Python File
        elif name.endswith(".py"):
            return [sys.executable, str(target_path)], BOTS_DIR, "success"
            
        # Case 3: Single JS File
        elif name.endswith(".js"):
            return ["node", str(target_path)], BOTS_DIR, "success"
            
        return None, None, "❌ Unsupported file type!"

    def start_bot(self, name):
        """Start a hosted bot process"""
        cmd, cwd, msg = self.detect_run_config(name)
        if not cmd:
            return False, msg
            
        # Kill existing if running
        if name in self.processes:
            self.stop_bot(name)
        
        # Prepare log file
        log_path = LOGS_DIR / f"{name}.log"
        log_file = open(log_path, "w")
        
        # Prepare environment
        env = os.environ.copy()
        if name in self.env_vars:
            env.update(self.env_vars[name])
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=str(cwd),
            )
            self.processes[name] = process
            self.run_commands[name] = cmd
            self.working_dirs[name] = cwd
            self.start_times[name] = datetime.now(IST)
            self.restart_counts[name] = self.restart_counts.get(name, 0)
            if name not in self.auto_restart:
                self.auto_restart[name] = True
            
            return True, f"✅ `{name}` started successfully! PID: `{process.pid}`"
        except Exception as e:
            return False, f"❌ Failed to start: `{str(e)}`"
    
    def stop_bot(self, name):
        """Stop a bot process"""
        if name not in self.processes:
            return False, f"❌ `{name}` is not running!"
        
        proc = self.processes[name]
        try:
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
        
        del self.processes[name]
        self.start_times.pop(name, None)
        return True, f"🛑 `{name}` stopped successfully!"
    
    def restart_bot(self, name):
        """Restart a bot"""
        self.stop_bot(name)
        time.sleep(1)
        self.restart_counts[name] = self.restart_counts.get(name, 0) + 1
        return self.start_bot(name)
    
    def get_status(self, name):
        """Get status of a specific bot"""
        if name not in self.processes:
            return "🔴 STOPPED"
        
        proc = self.processes[name]
        if proc.poll() is None:
            return "🟢 RUNNING"
        else:
            return "💀 CRASHED"
    
    def get_all_status(self):
        """Get status of all deployed projects"""
        all_items = sorted(list(BOTS_DIR.iterdir()))
        result = []
        for path in all_items:
            # Skip hidden files
            if path.name.startswith("."):
                continue
            name = path.name
            # Render folder or scripts
            if path.is_dir() or name.endswith(".py") or name.endswith(".js"):
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
                    "is_dir": path.is_dir()
                })
        return result
    
    def get_logs(self, name, lines=50):
        """Get last N lines of logs"""
        log_path = LOGS_DIR / f"{name}.log"
        if not log_path.exists():
            return "📭 No logs found."
        
        try:
            with open(log_path, "r", errors="ignore") as f:
                all_lines = f.readlines()
                last_lines = all_lines[-lines:]
                return "".join(last_lines) if last_lines else "📭 Log file is empty."
        except Exception as e:
            return f"❌ Error reading logs: {str(e)}"
    
    def clear_logs(self, name):
        """Clear log file"""
        log_path = LOGS_DIR / f"{name}.log"
        try:
            open(log_path, "w").close()
            return True
        except Exception:
            return False
    
    def delete_bot(self, name):
        """Delete bot files/directories and logs"""
        self.stop_bot(name)
        
        target_path = BOTS_DIR / name
        log_path = LOGS_DIR / f"{name}.log"
        env_path = ENV_DIR / f"{name}.env"
        
        try:
            if target_path.exists():
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()
            log_path.unlink(missing_ok=True)
            env_path.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Error deleting {name}: {e}")
        
        for d in [self.processes, self.start_times, self.restart_counts, 
                  self.auto_restart, self.env_vars, self.run_commands, self.working_dirs]:
            d.pop(name, None)
        
        return True
    
    def get_file_size(self, name):
        """Get size of file or directory"""
        target_path = BOTS_DIR / name
        if not target_path.exists():
            return "N/A"
            
        if target_path.is_file():
            size = target_path.stat().st_size
        else:
            size = sum(f.stat().st_size for f in target_path.glob('**/*') if f.is_file())
            
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        else:
            return f"{size/(1024*1024):.1f} MB"


# Global process manager
PM = ProcessManager()


# ================== 🔄 AUTO-RESTART DAEMON ==================
def auto_restart_daemon():
    """Background thread that auto-restarts crashed projects"""
    while True:
        try:
            for name in list(PM.processes.keys()):
                proc = PM.processes.get(name)
                if proc and proc.poll() is not None:
                    if PM.auto_restart.get(name, True):
                        logger.info(f"🔄 Auto-restarting crashed project: {name}")
                        PM.restart_counts[name] = PM.restart_counts.get(name, 0) + 1
                        
                        if PM.restart_counts[name] > 10:
                            logger.warning(f"⚠️ {name} crashed 10+ times. Disabling auto-restart.")
                            PM.auto_restart[name] = False
                            del PM.processes[name]
                            continue
                        
                        PM.start_bot(name)
        except Exception as e:
            logger.error(f"Auto-restart daemon error: {e}")
        
        time.sleep(15)


# ================== 🌐 FLASK KEEP-ALIVE ==================
web_app = Flask(__name__)

@web_app.route("/")
def index():
    running = sum(1 for p in PM.processes.values() if p.poll() is None)
    total = len([x for x in BOTS_DIR.iterdir() if not x.name.startswith(".")])
    return f"""
    <html>
    <head><title>{BOT_NAME}</title></head>
    <body style="background:#1a1a2e;color:#eee;font-family:monospace;padding:40px;text-align:center;">
        <h1>🚀 {BOT_NAME}</h1>
        <p>Version: {BOT_VERSION}</p>
        <hr style="border-color:#333">
        <p>🟢 Running Projects: <b>{running}</b></p>
        <p>📁 Total Deployed: <b>{total}</b></p>
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
            InlineKeyboardButton("📁 My Projects", callback_data="my_bots"),
        ],
        [
            InlineKeyboardButton("📥 Upload Project", callback_data="upload_info"),
            InlineKeyboardButton("🖥️ System Info", callback_data="system_info"),
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


def bot_action_kb(name):
    status = PM.get_status(name)
    ar = PM.auto_restart.get(name, True)
    ar_text = "🟢 Auto-Restart: ON" if ar else "🔴 Auto-Restart: OFF"
    
    buttons = []
    if "RUNNING" in status:
        buttons.append([
            InlineKeyboardButton("⏹️ Stop", callback_data=f"stop_{name}"),
            InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{name}"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton("▶️ Start", callback_data=f"start_{name}"),
        ])
    
    buttons.extend([
        [
            InlineKeyboardButton("📋 Logs (30 L)", callback_data=f"logs30_{name}"),
            InlineKeyboardButton("📋 Logs (100 L)", callback_data=f"logs100_{name}"),
        ],
        [
            InlineKeyboardButton("🧹 Clear Logs", callback_data=f"clearlogs_{name}"),
            InlineKeyboardButton(ar_text, callback_data=f"togglear_{name}"),
        ],
        [
            InlineKeyboardButton("📥 Download Backup", callback_data=f"download_{name}"),
            InlineKeyboardButton("🗑️ Delete Project", callback_data=f"confirmdelete_{name}"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh Status", callback_data=f"botinfo_{name}"),
            InlineKeyboardButton("🔙 Back List", callback_data="my_bots"),
        ],
    ])
    return InlineKeyboardMarkup(buttons)


def confirm_delete_kb(name):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Delete!", callback_data=f"delete_{name}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"botinfo_{name}"),
        ]
    ])


def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ])


def settings_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Restart Panel Bot", callback_data="restart_host"),
        ],
        [
            InlineKeyboardButton("🧹 Clean All Logs", callback_data="clean_all_logs"),
            InlineKeyboardButton("📊 Process List", callback_data="process_list"),
        ],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])


# ================== 🚀 HANDLERS ==================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    running = sum(1 for p in PM.processes.values() if p.poll() is None)
    total = len([x for x in BOTS_DIR.iterdir() if not x.name.startswith(".")])
    sys_info = get_system_info()

    txt = (
        f"<code>{BANNER}</code>\n\n"
        f"👋 Welcome, <b>{safe_name(user)}</b>!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Quick Stats:</b>\n"
        f"  📁 Total Projects: <code>{total}</code>\n"
        f"  🟢 Running: <code>{running}</code>\n"
        f"  🔴 Stopped: <code>{total - running}</code>\n\n"
        f"🖥️ <b>Server Resources:</b>\n"
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
            f"📭 No projects uploaded yet.\n\n"
            f"📥 Send <code>.py</code>, <code>.js</code>, or <code>.zip</code> file to deploy!"
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
        type_lbl = "📁 Directory" if bot["is_dir"] else ("🐍 Python" if bot["name"].endswith(".py") else "⚡ Node")
        txt += (
            f"{bot['status']} <code>{html.escape(bot['name'])}</code> ({type_lbl})\n"
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
    all_status = PM.get_all_status()
    if not all_status:
        await safe_edit(
            q,
            f"<code>{BANNER_MINI}</code>\n\n"
            f"📁 <b>MY PROJECTS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📭 No projects found.\n\n"
            f"📥 Send a <code>.py</code>, <code>.js</code>, or <code>.zip</code> file!",
            back_kb(),
        )
        return

    buttons = []
    for bot in all_status:
        name = bot["name"]
        status = bot["status"]
        icon = "🟢" if "RUNNING" in status else ("💀" if "CRASHED" in status else "🔴")
        buttons.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"botinfo_{name}")])

    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📁 <b>MY PROJECTS ({len(all_status)})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 Tap on any project to manage:",
        InlineKeyboardMarkup(buttons),
    )


# ================== 🤖 BOT INFO ==================
async def bot_info_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("botinfo_", "")
    status = PM.get_status(name)
    size = PM.get_file_size(name)
    ar = "🟢 ON" if PM.auto_restart.get(name, True) else "🔴 OFF"
    restarts = PM.restart_counts.get(name, 0)
    
    uptime_str = "N/A"
    pid_str = "N/A"
    if name in PM.processes and PM.processes[name].poll() is None:
        pid_str = str(PM.processes[name].pid)
        if name in PM.start_times:
            delta = datetime.now(IST) - PM.start_times[name]
            h, rem = divmod(int(delta.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            uptime_str = f"{h}h {m}m {s}s"

    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🤖 <b>PROJECT MANAGEMENT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 <b>Project Name:</b> <code>{html.escape(name)}</code>\n"
        f"📊 <b>Status:</b> {status}\n"
        f"🆔 <b>PID:</b> <code>{pid_str}</code>\n"
        f"⏱️ <b>Uptime:</b> <code>{uptime_str}</code>\n"
        f"📦 <b>Storage Size:</b> <code>{size}</code>\n"
        f"🔄 <b>Auto-Restart:</b> {ar}\n"
        f"🔢 <b>Total Restarts:</b> <code>{restarts}</code>\n\n"
        f"⏰ <code>{now_ist()}</code>"
    )
    await safe_edit(q, txt, bot_action_kb(name))


# ================== ▶️ START/STOP/RESTART SINGLE ==================
async def start_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Starting...")
    name = q.data.replace("start_", "")
    ok, msg = PM.start_bot(name)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n{msg}\n\n⏰ <code>{now_ist()}</code>",
        bot_action_kb(name),
    )


async def stop_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Stopping...")
    name = q.data.replace("stop_", "")
    ok, msg = PM.stop_bot(name)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n{msg}\n\n⏰ <code>{now_ist()}</code>",
        bot_action_kb(name),
    )


async def restart_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Restarting...")
    name = q.data.replace("restart_", "")
    ok, msg = PM.restart_bot(name)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n{msg}\n\n⏰ <code>{now_ist()}</code>",
        bot_action_kb(name),
    )


# ================== 📋 LOGS VIEWER ==================
async def view_logs_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data.startswith("logs30_"):
        name = data.replace("logs30_", "")
        lines = 30
    elif data.startswith("logs100_"):
        name = data.replace("logs100_", "")
        lines = 100
    else:
        return

    logs = PM.get_logs(name, lines)
    safe_logs = html.escape(logs)
    if len(safe_logs) > 3500:
        safe_logs = safe_logs[-3500:]
        safe_logs = "...(truncated)\n" + safe_logs

    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📋 <b>LOGS:</b> <code>{html.escape(name)}</code>\n"
        f"📏 Last <b>{lines}</b> lines\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<pre>{safe_logs}</pre>"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=q.data),
            InlineKeyboardButton("🧹 Clear Logs", callback_data=f"clearlogs_{name}"),
        ],
        [InlineKeyboardButton("🔙 Project Settings", callback_data=f"botinfo_{name}")],
    ])
    await safe_edit(q, txt, kb)


async def clear_logs_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Logs cleared!")
    name = q.data.replace("clearlogs_", "")
    PM.clear_logs(name)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🧹 Logs for <code>{html.escape(name)}</code> cleared!",
        InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Management", callback_data=f"botinfo_{name}")]
        ]),
    )


# ================== 🔄 AUTO-RESTART TOGGLE ==================
async def toggle_ar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    name = q.data.replace("togglear_", "")
    current = PM.auto_restart.get(name, True)
    PM.auto_restart[name] = not current
    new_state = "ON 🟢" if PM.auto_restart[name] else "OFF 🔴"

    await q.answer(f"Auto-Restart: {new_state}")
    q.data = f"botinfo_{name}"
    await bot_info_cb(update, context)


# ================== 🗑️ DELETE BOT ==================
async def confirm_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.replace("confirmdelete_", "")
    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"⚠️ <b>CONFIRM PROJECTS DELETION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🗑️ Are you sure you want to <b>permanently delete</b>:\n"
        f"📁 <code>{html.escape(name)}</code>\n\n"
        f"⚠️ This will:\n"
        f"  • Stop running process instantly\n"
        f"  • Delete entire folder / single script files\n"
        f"  • Delete all runtime log history\n\n"
        f"❌ <b>This action CANNOT be undone!</b>",
        confirm_delete_kb(name),
    )


async def delete_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Deleted!")
    name = q.data.replace("delete_", "")
    PM.delete_bot(name)

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🗑️ <code>{html.escape(name)}</code> <b>successfully deleted!</b>",
        back_kb(),
    )


# ================== 📤 DOWNLOAD BOT FILE/ZIP ==================
async def download_bot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Archiving and sending...")
    name = q.data.replace("download_", "")
    target_path = BOTS_DIR / name

    if not target_path.exists():
        await safe_edit(q, "❌ Project files not found!", back_kb())
        return

    # If it's a file, send directly. If directory, zip it and send.
    if target_path.is_file():
        try:
            await context.bot.send_document(
                chat_id=q.from_user.id,
                document=open(target_path, "rb"),
                filename=name,
                caption=f"📤 <b>File Backup:</b> <code>{html.escape(name)}</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            await safe_edit(q, f"❌ Failed to send file: {str(e)}", back_kb())
    else:
        # Create temp zip file
        temp_zip_path = Path(f"{name}_backup.zip")
        try:
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(target_path):
                    for file in files:
                        file_abs_path = Path(root) / file
                        arcname = file_abs_path.relative_to(target_path)
                        zipf.write(file_abs_path, arcname)
                        
            await context.bot.send_document(
                chat_id=q.from_user.id,
                document=open(temp_zip_path, "rb"),
                filename=f"{name}.zip",
                caption=f"📤 <b>Project ZIP Backup:</b> <code>{html.escape(name)}</code>",
                parse_mode="HTML",
            )
        except Exception as e:
            await safe_edit(q, f"❌ Failed to send ZIP: {str(e)}", back_kb())
        finally:
            temp_zip_path.unlink(missing_ok=True)


# ================== ▶️⏹️🔄 BULK ACTIONS ==================
async def start_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Starting all...")
    all_items = list(BOTS_DIR.iterdir())
    started = 0
    failed = 0
    for item in all_items:
        if item.name.startswith("."):
            continue
        if item.is_dir() or item.name.endswith(".py") or item.name.endswith(".js"):
            ok, _ = PM.start_bot(item.name)
            if ok:
                started += 1
            else:
                failed += 1

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"▶️ <b>START ALL PROJECTS RESULTS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Started successfully: <code>{started}</code>\n"
        f"❌ Failed / Bad configuration: <code>{failed}</code>\n",
        back_kb(),
    )


async def stop_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Stopping all...")
    stopped = 0
    for name in list(PM.processes.keys()):
        ok, _ = PM.stop_bot(name)
        if ok:
            stopped += 1

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"⏹️ <b>ALL PROJECTS RUNTIME STOPPED</b>\n\n"
        f"🛑 Stopped: <code>{stopped}</code> processes",
        back_kb(),
    )


async def restart_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Restarting all...")
    all_items = list(BOTS_DIR.iterdir())
    restarted = 0
    for item in all_items:
        if item.name.startswith("."):
            continue
        if item.is_dir() or item.name.endswith(".py") or item.name.endswith(".js"):
            ok, _ = PM.restart_bot(item.name)
            if ok:
                restarted += 1

    await safe_edit(
        q,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🔄 <b>ALL RUNNING BOTS RESTARTED</b>\n\n"
        f"✅ Restarted: <code>{restarted}</code> services",
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
        f"🖥️ <b>SYSTEM MONITOR RESOURCES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💻 <b>CPU Usage:</b>\n"
        f"   <code>[{cpu_bar}]</code> <b>{cpu_pct}%</b>\n\n"
        f"🧠 <b>RAM Usage:</b>\n"
        f"   <code>[{ram_bar}]</code> <b>{ram_pct}%</b>\n"
        f"   📊 {info['ram_used']} / {info['ram_total']} MB\n\n"
        f"💾 <b>Disk Capacity:</b>\n"
        f"   <code>[{disk_bar}]</code> <b>{disk_pct}%</b>\n"
        f"   📊 {info['disk_used']} / {info['disk_total']} GB\n\n"
        f"🤖 <b>Active Threads Running:</b> <code>{running}</code>\n"
        f"🐍 <b>Python Runtime:</b> <code>{sys.version.split()[0]}</code>\n"
        f"💻 <b>Architecture:</b> <code>{sys.platform}</code>\n\n"
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
        f"📥 <b>HOW TO DEPLOY BOTS & ZIP FILES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"1️⃣ <b>Single Code Files:</b>\n"
        f"  • Send <code>.py</code> (Python) ya <code>.js</code> (Node.js) file as Document.\n\n"
        f"2️⃣ <b>Project ZIP Archives:</b>\n"
        f"  • Poore project folder ko `.zip` file me archive karke send karein.\n"
        f"  • Zip ke andr ek standard main entry file hona zaroori hai:\n"
        f"    (Jaise: <code>main.py</code>, <code>bot.py</code>, <code>index.js</code> ya <code>app.js</code>)\n\n"
        f"🚀 <b>Deploy Process:</b>\n"
        f"Bot auto-extract karke dependencies, paths or scripts ko self-execute aur manage karega!\n\n"
        f"📁 Document send karein niche! 👇",
        back_kb(),
    )


# ================== 📥 FILE/ZIP UPLOAD HANDLER ==================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    original_name = doc.file_name
    if not original_name or not (original_name.endswith(".py") or original_name.endswith(".js") or original_name.endswith(".zip")):
        await safe_reply(
            update,
            "❌ <b>Invalid File!</b>\n\n"
            "Sirf <code>.py</code>, <code>.js</code>, ya <code>.zip</code> archive files bhejein!",
        )
        return

    # Check file size (max 15 MB for complete ZIP projects)
    if doc.file_size and doc.file_size > 15 * 1024 * 1024:
        await safe_reply(
            update,
            "❌ <b>File too large!</b>\n\n"
            "Maximum project ZIP file limit: <code>15 MB</code>",
        )
        return

    status_msg = await safe_reply(
        update,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"⏳ <b>Downloading</b> <code>{html.escape(original_name)}</code>...\n\n"
        f"<code>[██████░░░░░░░░░░░░░░]</code> 30%",
    )

    # 1. Download to dynamic temp directory
    temp_target = Path(f"temp_{original_name}")
    tg_file = await doc.get_file()
    await tg_file.download_to_drive(str(temp_target))

    project_name = original_name
    is_zip = original_name.endswith(".zip")
    
    if is_zip:
        project_name = original_name[:-4]  # Remove .zip extension to get folder name
        target_dir = BOTS_DIR / project_name
        
        # Stop bot if already running
        if project_name in PM.processes:
            PM.stop_bot(project_name)
            
        # Extract safely
        await safe_edit(
            status_msg,
            f"<code>{BANNER_MINI}</code>\n\n"
            f"📦 <b>Extracting</b> <code>{html.escape(original_name)}</code>...\n\n"
            f"<code>[██████████████░░░░░░]</code> 70%",
        )
        
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(temp_target, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
        except Exception as e:
            temp_target.unlink(missing_ok=True)
            await safe_edit(status_msg, f"❌ ZIP extract failure: {str(e)}", back_kb())
            return
            
        temp_target.unlink() # Delete temp zip
    else:
        # For single script files (.py/.js)
        target_file = BOTS_DIR / original_name
        if project_name in PM.processes:
            PM.stop_bot(project_name)
        shutil.move(str(temp_target), str(target_file))

    # Update progress
    await safe_edit(
        status_msg,
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📥 <b>Deploying project:</b> Starting services...\n\n"
        f"<code>[██████████████████░░]</code> 90%",
    )

    # Start the application
    await asyncio.sleep(0.5)
    ok, msg = PM.start_bot(project_name)

    if ok:
        await asyncio.sleep(2)
        status = PM.get_status(project_name)

        if "RUNNING" in status:
            cmd_args = " ".join(PM.run_commands[project_name])
            final_text = (
                f"<code>{BANNER_MINI}</code>\n\n"
                f"✅ <b>PROJECT DEPLOYED & LIVE!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📁 <b>Project:</b> <code>{html.escape(project_name)}</code>\n"
                f"⚙️ <b>Command:</b> <code>{html.escape(cmd_args)}</code>\n"
                f"📦 <b>Total Size:</b> <code>{PM.get_file_size(project_name)}</code>\n"
                f"🆔 <b>PID:</b> <code>{PM.processes[project_name].pid}</code>\n"
                f"🟢 <b>Status:</b> Active Running\n\n"
                f"<code>[████████████████████]</code> 100% ✅\n\n"
                f"⏰ <code>{now_ist()}</code>"
            )
        else:
            # immediate crash logs
            logs = PM.get_logs(project_name, 20)
            safe_logs = html.escape(logs)[:1500]
            final_text = (
                f"<code>{BANNER_MINI}</code>\n\n"
                f"⚠️ <b>PROJECT START ERROR / CRASHED</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📁 Project: <code>{html.escape(project_name)}</code>\n"
                f"💀 Status: Immediate Crash\n\n"
                f"📋 <b>Crash Stack Trace:</b>\n"
                f"<pre>{safe_logs}</pre>"
            )
    else:
        final_text = (
            f"<code>{BANNER_MINI}</code>\n\n"
            f"❌ <b>FAILED TO DEPLOY APPLICATION:</b>\n\n{msg}"
        )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Manage Project", callback_data=f"botinfo_{project_name}")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])
    await safe_edit(status_msg, final_text, kb)


# ================== 🗑️ FILE MANAGER ==================
async def file_manager_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    all_status = PM.get_all_status()
    log_files = sorted(LOGS_DIR.glob("*.log"))

    log_size = sum(f.stat().st_size for f in log_files) / 1024

    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"🗑️ <b>SERVER FILE MANAGER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📁 <b>Deployed Projects:</b> <code>{len(all_status)}</code>\n"
        f"📋 <b>Log Archives:</b> <code>{len(log_files)}</code> "
        f"({log_size:.1f} KB)\n\n"
    )

    for bot in all_status:
        name = bot["name"]
        size = PM.get_file_size(name)
        status = bot["status"]
        icon = "🟢" if "RUNNING" in status else "🔴"
        type_str = "📂 Dir" if bot["is_dir"] else "📄 File"
        txt += f"  {icon} <code>{html.escape(name)}</code> ({type_str} | {size})\n"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧹 Purge ALL Logs", callback_data="clean_all_logs")],
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
        f"⚙️ <b>CONTROL PANEL SETTINGS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Live Thread:</b> <code>{running}</code>\n"
        f"🔄 <b>Auto-Restart Pool:</b> <code>{ar_on}</code>\n"
        f"🐍 <b>Main Runtime:</b> <code>{sys.version.split()[0]}</code>\n"
        f"📂 <b>Bot Path:</b> <code>{BOTS_DIR}</code>\n"
        f"📋 <b>Logs Path:</b> <code>{LOGS_DIR}</code>\n\n"
        f"👑 <b>Server Owners:</b> {', '.join(f'<code>{a}</code>' for a in ADMIN_IDS)}",
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
        f"🧹 <b>System Logs Cleaned!</b>\n\n"
        f"📋 Purged: <code>{count}</code> log files",
        back_kb(),
    )


async def process_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = (
        f"<code>{BANNER_MINI}</code>\n\n"
        f"📊 <b>SERVER PROCESS ALLOCATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not PM.processes:
        txt += "📭 No active running processes."
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
                        f"RAM allocation: <code>{mem:.1f} MB</code> | "
                        f"CPU use: <code>{cpu}%</code>\n\n"
                    )
                else:
                    txt += (
                        f"{icon} <code>{html.escape(name)}</code>\n"
                        f"   PID: <code>{pid}</code> | Status: Terminated\n\n"
                    )
            except Exception:
                txt += (
                    f"{icon} <code>{html.escape(name)}</code>\n"
                    f"   PID: <code>{pid}</code>\n\n"
                )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Processes", callback_data="process_list")],
        [InlineKeyboardButton("🔙 Panel Settings", callback_data="settings")],
    ])
    await safe_edit(q, txt, kb)


# ================== ❓ HELP ==================
async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await safe_edit(
        q,
        f"<code>{BANNER}</code>\n\n"
        f"❓ <b>HELP GUIDE & DEPLOY MANUAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📥 <b>Project Upload:</b>\n"
        f"  Python (`.py`), JS (`.js`) scripts ya ZIP files ko as Document direct chat me forward/upload karein.\n\n"
        f"⚙️ <b>Dashboard Navigation:</b>\n"
        f"  📂 My Projects pe jao -> Apne scripts/deployments ke andr control elements navigate karein.\n\n"
        f"🔧 <b>Advanced Terminal Options:</b>\n"
        f"  ▶️ bulk actions (Start/Stop/Restart all)\n"
        f"  📋 Logs review (last 30/100 lines compile)\n"
        f"  🧹 Dynamic Auto-Restart thread parameters\n"
        f"  📥 Dynamic ZIP archiving download option\n\n"
        f"🔧 <b>Core Engine:</b> <code>v{BOT_VERSION}</code>",
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
        
        # Stop propagating further
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

    # Dynamic bot action callbacks (Optimized dynamic routing)
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

    # Event loop fallback configurations for Python 3.12+ / 3.14 (Render Support)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    print("🚀 Bot is ONLINE! Polling started...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
