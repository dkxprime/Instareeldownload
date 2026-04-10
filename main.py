import os
import re
import time
import logging
import yt_dlp
from threading import Thread
from flask import Flask
from tinydb import TinyDB, Query
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ===== CONFIG =====
BOT_TOKEN = "7553132504:AAFbfizSUruFKvaq-jZ-Xkc7ilJWjXpwCos"
ADMIN_ID = 6663149518
CHANNEL_URL = "https://t.me/instasaverb"

USER_LIMIT = 3

db = TinyDB('db.json')
User = Query()

# ===== WEB =====
web = Flask(__name__)

@web.route('/')
def home():
    return "Bot Running"

def run_web():
    web.run(host="0.0.0.0", port=8080)

logging.basicConfig(level=logging.INFO)

# ===== USER =====
def get_user(uid):
    u = db.search(User.id == uid)
    return u[0] if u else None

def create_user(uid, username):
    if not get_user(uid):
        db.insert({
            "id": uid,
            "username": username,
            "downloads": 0,
            "vip": False,
            "blocked": False,
            "utr": "",
            "date": time.ctime()
        })

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username)

    keyboard = [
        [InlineKeyboardButton("💎 Buy VIP", callback_data="buy")],
        [InlineKeyboardButton("📊 Status", callback_data="status")]
    ]

    await update.message.reply_text(
        "🔥 INSTASAVER BOT 🔥\n\n"
        "Send any link to download\n\n"
        "👤 Free: 3 downloads/day\n"
        "💎 VIP: Unlimited + HD",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== DOWNLOAD =====
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    url = update.message.text

    if not re.match(r'http', url):
        return await update.message.reply_text("❌ Send valid link")

    user = get_user(uid)

    if user['blocked']:
        return await update.message.reply_text("🚫 Blocked")

    if not user['vip'] and user['downloads'] >= USER_LIMIT:
        return await update.message.reply_text("❌ Limit reached. Buy VIP.")

    msg = await update.message.reply_text("⏳ Processing...")

    try:
        if not os.path.exists("downloads"):
            os.makedirs("downloads")

        fmt = "best" if user['vip'] else "best[height<=720]"
        ydl_opts = {'format': fmt, 'outtmpl': 'downloads/%(title)s.%(ext)s'}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file = ydl.prepare_filename(info)

        await msg.edit_text("📤 Uploading...")

        with open(file, "rb") as f:
            if file.endswith(('.jpg','.png','.jpeg')):
                await context.bot.send_photo(uid, f)
            else:
                await context.bot.send_video(uid, f)

        os.remove(file)

        db.update({'downloads': user['downloads'] + 1}, User.id == uid)

        if not user['vip']:
            await context.bot.send_message(uid, "💰 Ad: https://your-link.com")

        await msg.delete()

    except Exception as e:
        logging.error(e)
        await msg.edit_text("❌ Failed")

# ===== CALLBACK =====
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    if q.data == "buy":
        await context.bot.send_photo(
            chat_id=uid,
            photo=open("qr.jpg", "rb"),
            caption="💎 Pay ₹49\n\nAfter payment send UTR number here."
        )

# ===== UTR HANDLER =====
async def handle_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()

    # basic UTR validation (numbers 10-20 length)
    if not re.match(r'^\d{10,20}$', text):
        return

    # check duplicate UTR
    all_users = db.all()
    for u in all_users:
        if u.get("utr") == text:
            return await update.message.reply_text("❌ UTR already used")

    db.update({'utr': text}, User.id == uid)

    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")]
    ]

    await context.bot.send_message(
        ADMIN_ID,
        f"💰 New Payment\nUser: {uid}\nUTR: {text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("📩 Sent for verification")

# ===== ADMIN CALLBACK =====
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    if q.data.startswith("approve_"):
        uid = int(q.data.split("_")[1])
        db.update({'vip': True}, User.id == uid)

        await context.bot.send_message(uid, "🎉 VIP Activated!")
        await q.message.edit_text("✅ Approved")

    elif q.data.startswith("reject_"):
        uid = int(q.data.split("_")[1])
        db.update({'utr': ""}, User.id == uid)

        await context.bot.send_message(uid, "❌ Rejected")
        await q.message.edit_text("❌ Rejected")

# ===== ADMIN =====
async def stats(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"Users: {len(db.all())}")

# ===== MAIN =====
if __name__ == "__main__":
    Thread(target=run_web).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(MessageHandler(filters.TEXT, handle_utr))

    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(CallbackQueryHandler(admin_callback))

    print("🔥 Bot Running")
    app.run_polling()def download_video(url):
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not db.search(User.id == user.id):
        db.insert({'id': user.id, 'username': user.username, 'date': time.ctime()})

    if not await is_subscribed(user.id, context):
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
                    [InlineKeyboardButton("🔄 Verify Join", callback_data="verify")]]
        return await update.message.reply_text(
            f"👋 **Hi {user.first_name}!**\n\n⚠️ **ACCESS LOCKED**\n\nIs bot ko use karne ke liye hamara VIP channel join karein.",
            reply_markup=InlineKeyboardMarkup(keyboard))

    await update.message.reply_text(
        "🔥 **INSTASAVER ALL-IN-ONE DOWNLOADER** 🔥\n\n"
        "Bhai, kisi bhi video ka link paste karo:\n"
        "✅ **Instagram Reels**\n"
        "✅ **YouTube Shorts / Video**\n"
        "✅ **TikTok / Facebook / Twitter**\n\n"
        "⚡ *Bas link bhej aur magic dekh!*",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 My Profile", callback_data="stats")]])
    )

# --- ADMIN FEATURE ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    total_users = len(db.all())
    await update.message.reply_text(
        f"👑 **ADMIN DASHBOARD**\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"🤖 Status: `Running Smooth`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Broadcast", callback_data="bc_msg")]])
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return await update.message.reply_text("Format: `/broadcast Hello Users`")
    
    msg = " ".join(context.args)
    users = db.all()
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(u['id'], f"📢 **ANNOUNCEMENT**\n\n{msg}")
            sent += 1
        except: pass
    await update.message.reply_text(f"✅ Success: {sent} users.")

# --- DOWNLOAD LOGIC ---
async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_subscribed(user_id, context): return await start(update, context)

    url = update.message.text
    if not re.match(r'http', url): return
    
    status_msg = await update.message.reply_text("⏳ **Processing... Please wait.**")
    
    try:
        # Create directory if not exists
        if not os.path.exists('downloads'): os.makedirs('downloads')
        
        file_path = download_video(url)
        await status_msg.edit_text("📤 **Uploading to Telegram...**")
        
        with open(file_path, 'rb') as video:
            await context.bot.send_video(
                chat_id=user_id, 
                video=video, 
                caption=f"✅ **Downloaded by @SepaxYt_Bot**\n\n🔥 Join: {CHANNEL_URL}"
            )
        
        os.remove(file_path) # Clean up
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text("❌ **Sorry!** Video download nahi ho payi. Link check karein ya dusra try karein.")

# --- CALLBACKS ---
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "verify":
        if await is_subscribed(query.from_user.id, context):
            await query.message.edit_text("✅ **Verification Success!** Ab link bhejo.")
        else:
            await query.answer("❌ Abhi tak join nahi kiya!", show_alert=True)
            
    elif query.data == "stats":
        u = db.search(User.id == query.from_user.id)[0]
        await query.message.reply_text(f"👤 **User:** {query.from_user.first_name}\n📅 **Joined:** {u['date']}")

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_web).start()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_download))
    app.add_handler(CallbackQueryHandler(callbacks))
    
    print("SepaxYt Downloader Started!")
    app.run_polling()
