# KM Rank Bot — Python / Pydroid 3
# Install first: pip install python-telegram-bot
# Put your BotFather token in BOT_TOKEN below. Do not share it.

import logging
import os
import sqlite3
from datetime import timedelta
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
DB_NAME = os.environ.get("DB_PATH", "km_ranks.sqlite3")

RANKS = [
    "Admin", "Supervisor", "Lider_1_2", "Co_Lider", "KM_Chiff",
    "Sinyor_KM", "KM_Member", "Member", "Tobikh_1", "Tobikh"
]
LEVEL = {rank: i for i, rank in enumerate(RANKS)}
# These are bot-managed group ranks. Telegram still controls real admin permissions.
HELP = """
🤖 KM Rank Bot

دستورها:
 /setup — ثبت مالک گروه (فقط مالک واقعی گروه)
 /setrank @username Rank — تعیین رنک
 /rank [@username] — مشاهده رنک
 /ranks — فهرست رنک‌های ثبت‌شده
 /mute @username 10 — محدودکردن کاربر برای چند دقیقه
 /unmute @username — برداشتن محدودیت
 /pin — سنجاق پیام (روی پیام موردنظر ریپلای کن)
 /invite — ساخت لینک دعوت

رنک‌ها:
Admin, Supervisor, Lider_1_2, Co_Lider, KM_Chiff,
Sinyor_KM, KM_Member, Member, Tobikh_1, Tobikh
"""

logging.basicConfig(level=logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)
log = logging.getLogger(__name__)

def db():
    con = sqlite3.connect(DB_NAME)
    con.execute("""CREATE TABLE IF NOT EXISTS groups_data (
        chat_id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS ranks (
        chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
        username TEXT, display_name TEXT, rank TEXT NOT NULL,
        PRIMARY KEY(chat_id, user_id))""")
    con.commit()
    return con

def get_owner(chat_id):
    with db() as con:
        row = con.execute("SELECT owner_id FROM groups_data WHERE chat_id=?",
                          (chat_id,)).fetchone()
    return row[0] if row else None

def get_rank(chat_id, user_id):
    with db() as con:
        row = con.execute("SELECT rank FROM ranks WHERE chat_id=? AND user_id=?",
                          (chat_id, user_id)).fetchone()
    if row:
        return row[0]
    if get_owner(chat_id) == user_id:
        return "Supervisor"
    return "Member"

def save_rank(chat_id, user, rank):
    with db() as con:
        con.execute("""INSERT INTO ranks(chat_id,user_id,username,display_name,rank)
          VALUES(?,?,?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET
          username=excluded.username, display_name=excluded.display_name,
          rank=excluded.rank""",
          (chat_id, user.id, user.username, user.full_name, rank))
        con.commit()

async def group_only(update):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text("این دستور را داخل گروه اجرا کن.")
        return False
    return True

async def is_real_group_owner(update, context):
    chat, user = update.effective_chat, update.effective_user
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status == "creator"
    except Exception:
        return False

async def setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update):
        return
    chat, user = update.effective_chat, update.effective_user
    if not await is_real_group_owner(update, context):
        await update.message.reply_text("فقط مالک واقعی گروه می‌تواند /setup را اجرا کند.")
        return
    with db() as con:
        con.execute("INSERT OR REPLACE INTO groups_data(chat_id,owner_id) VALUES(?,?)",
                    (chat.id, user.id))
        con.commit()
    save_rank(chat.id, user, "Supervisor")
    await update.message.reply_text(
        f"✅ مالک گروه ثبت شد: {user.full_name}\nرنک شما: Supervisor\n"
        "اکنون می‌توانی با /setrank به اعضا رنک بدهی."
    )

async def target_from_command(update, context):
    # Preferred: reply to a user's message, then /setrank Rank
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if context.args:
            return msg.reply_to_message.from_user, context.args[0]
        return msg.reply_to_message.from_user, None
    # Alternative: /setrank @username Rank — username must be known to the bot
    if len(context.args) >= 2 and context.args[0].startswith("@"):
        username = context.args[0][1:].lower()
        with db() as con:
            row = con.execute(
                "SELECT user_id, username, display_name FROM ranks WHERE chat_id=? AND lower(username)=?",
                (update.effective_chat.id, username)).fetchone()
        if row:
            class UserStub:
                pass
            u = UserStub()
            u.id, u.username, u.full_name = row[0], row[1], row[2]
            return u, context.args[1]
        await msg.reply_text("این کاربر هنوز در دیتابیس رنک‌ها نیست. روی پیام او ریپلای کن و بنویس: /setrank Rank")
        return None, None
    return None, None

async def setrank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update):
        return
    chat, actor = update.effective_chat, update.effective_user
    owner = get_owner(chat.id)
    if owner is None:
        await update.message.reply_text("ابتدا مالک گروه باید /setup را اجرا کند.")
        return
    actor_rank = get_rank(chat.id, actor.id)
    target, new_rank = await target_from_command(update, context)
    if target is None:
        await update.message.reply_text(
            "روش پیشنهادی: روی پیام عضو ریپلای کن و بنویس:\n"
            "/setrank KM_Chiff\n\nیا اگر کاربر قبلاً ثبت شده:\n/setrank @username KM_Chiff"
        )
        return
    if new_rank not in RANKS:
        await update.message.reply_text("رنک نامعتبر است.\nرنک‌ها:\n" + ", ".join(RANKS))
        return
    if actor.id != owner and actor_rank != "Lider_1_2":
        await update.message.reply_text("⛔ فقط Supervisor و Lider_1_2 اجازه /setrank دارند.")
        return
    if actor.id != owner:
        if LEVEL[new_rank] < LEVEL["Co_Lider"]:
            await update.message.reply_text("⛔ لیدر فقط می‌تواند Co_Lider یا رنک‌های پایین‌تر بدهد.")
            return
        if target.id == owner or get_rank(chat.id, target.id) in ("Supervisor", "Lider_1_2"):
            await update.message.reply_text("⛔ نمی‌توانی رنک مالک یا لیدر را تغییر بدهی.")
            return
    if target.id == actor.id and actor.id != owner:
        await update.message.reply_text("⛔ نمی‌توانی رنک خودت را تغییر بدهی.")
        return
    if target.id == owner and new_rank != "Supervisor":
        await update.message.reply_text("رنک مالک اصلی قابل تغییر نیست.")
        return
    save_rank(chat.id, target, new_rank)
    await update.message.reply_text(f"✅ رنک {target.full_name} شد: {new_rank}")

async def rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update):
        return
    chat = update.effective_chat
    target = update.effective_message.reply_to_message.from_user if (
        update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user
    ) else update.effective_user
    rank = get_rank(chat.id, target.id)
    await update.message.reply_text(f"🏅 {target.full_name}\nRank: {rank}")

async def ranks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update):
        return
    chat = update.effective_chat
    with db() as con:
        rows = con.execute(
            "SELECT display_name, username, rank FROM ranks WHERE chat_id=?",
            (chat.id,)).fetchall()
    if not rows:
        await update.message.reply_text("هنوز رنکی ثبت نشده؛ مالک گروه /setup را اجرا کند.")
        return
    rows.sort(key=lambda r: LEVEL.get(r[2], 999))
    text = "🏆 رنک‌های گروه:\n\n"
    for i, (name, username, rank) in enumerate(rows, 1):
        text += f"{i}. {rank} — {name or 'Unknown'}"
        if username:
            text += f" (@{username})"
        text += "\n"
    await update.message.reply_text(text[:4000])

async def remember_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
        return
    msg = update.effective_message
    if not msg or not msg.from_user or msg.from_user.is_bot:
        return
    user = msg.from_user
    if user.id == get_owner(update.effective_chat.id):
        save_rank(update.effective_chat.id, user, "Supervisor")
    else:
        with db() as con:
            exists = con.execute("SELECT 1 FROM ranks WHERE chat_id=? AND user_id=?",
                                 (update.effective_chat.id, user.id)).fetchone()
        if not exists:
            save_rank(update.effective_chat.id, user, "Member")

async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update):
        return
    chat, actor, msg = update.effective_chat, update.effective_user, update.effective_message
    if get_rank(chat.id, actor.id) not in ("Supervisor", "Lider_1_2", "Co_Lider", "KM_Chiff"):
        await msg.reply_text("⛔ رنک شما اجازه محدودکردن کاربران را ندارد.")
        return
    if not msg.reply_to_message or not context.args:
        await msg.reply_text("روی پیام کاربر ریپلای کن و بنویس: /mute 10")
        return
    try:
        minutes = max(1, min(int(context.args[0]), 10080))
        target = msg.reply_to_message.from_user
        await context.bot.restrict_chat_member(
            chat.id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=timedelta(minutes=minutes)
        )
        await msg.reply_text(f"🔇 {target.full_name} برای {minutes} دقیقه محدود شد.")
    except Exception as e:
        await msg.reply_text("انجام نشد؛ ربات باید ادمین با مجوز Restrict members باشد.")

async def unmute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update):
        return
    chat, actor, msg = update.effective_chat, update.effective_user, update.effective_message
    if get_rank(chat.id, actor.id) not in ("Supervisor", "Lider_1_2", "Co_Lider", "KM_Chiff"):
        await msg.reply_text("⛔ دسترسی ندارید.")
        return
    if not msg.reply_to_message:
        await msg.reply_text("روی پیام کاربر ریپلای کن و بنویس: /unmute")
        return
    target = msg.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(
            chat.id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_audios=True, can_send_documents=True,
                can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await msg.reply_text(f"🔊 محدودیت {target.full_name} برداشته شد.")
    except Exception:
        await msg.reply_text("انجام نشد؛ ربات باید ادمین با مجوز Restrict members باشد.")

async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update):
        return
    chat, actor, msg = update.effective_chat, update.effective_user, update.effective_message
    if get_rank(chat.id, actor.id) not in ("Supervisor", "Lider_1_2", "Co_Lider", "KM_Chiff"):
        await msg.reply_text("⛔ رنک شما اجازه سنجاق پیام ندارد.")
        return
    if not msg.reply_to_message:
        await msg.reply_text("روی پیامی که می‌خواهی سنجاق شود ریپلای کن و بنویس: /pin")
        return
    try:
        await context.bot.pin_chat_message(chat.id, msg.reply_to_message.message_id)
        await msg.reply_text("📌 پیام سنجاق شد.")
    except Exception:
        await msg.reply_text("ربات باید ادمین با مجوز Pin messages باشد.")

async def invite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await group_only(update):
        return
    chat, actor = update.effective_chat, update.effective_user
    if get_rank(chat.id, actor.id) not in (
        "Supervisor", "Lider_1_2", "Co_Lider", "KM_Chiff", "Sinyor_KM", "KM_Member"
    ):
        await update.effective_message.reply_text("⛔ رنک شما اجازه ساخت لینک دعوت ندارد.")
        return
    try:
        link = await context.bot.create_chat_invite_link(chat.id)
        await update.effective_message.reply_text("🔗 لینک دعوت:\n" + link.invite_link)
    except Exception:
        await update.effective_message.reply_text("ربات باید ادمین با مجوز Invite users باشد.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_BOTFATHER_TOKEN_HERE":
        print("خطا: متغیر محیطی BOT_TOKEN در تنظیمات سرویس وارد نشده است.")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("setup", setup))
    app.add_handler(CommandHandler("setrank", setrank))
    app.add_handler(CommandHandler("rank", rank_cmd))
    app.add_handler(CommandHandler("ranks", ranks_cmd))
    app.add_handler(CommandHandler("mute", mute_cmd))
    app.add_handler(CommandHandler("unmute", unmute_cmd))
    app.add_handler(CommandHandler("pin", pin_cmd))
    app.add_handler(CommandHandler("invite", invite_cmd))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, remember_member))
    print("KM Rank Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
