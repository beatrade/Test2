
import os
import re
import json
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

TOKEN = "7982960933:AAFMVL_t5BhMDms-CxSkcuVNfQZnR77UJ6Q"
ADMIN_ID = 7272679429  # آیدی عددی ادمین
WALLET_ADDRESS = "TSaYwHFb9CiRJ1do52bm3KF15sLmrZ6Z25"

VIP_DB = "vip_users.json"
FREE_DB = "free_users.json"
DOWNLOAD_PATH = "downloads"
MAX_FILE_SIZE_MB = 50

os.makedirs(DOWNLOAD_PATH, exist_ok=True)

def load_json(file):
    if not os.path.exists(file): return {}
    with open(file, 'r') as f:
        return json.load(f)

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f)

def load_vips():
    return load_json(VIP_DB)

def save_vips(vips):
    save_json(VIP_DB, vips)

def is_vip(user_id):
    vips = load_vips()
    if str(user_id) in vips:
        exp = datetime.strptime(vips[str(user_id)], "%Y-%m-%d")
        return datetime.now() < exp
    return False

def add_vip(user_id):
    vips = load_vips()
    expiry = datetime.now() + timedelta(days=30)
    vips[str(user_id)] = expiry.strftime("%Y-%m-%d")
    save_vips(vips)

def count_free(user_id):
    return load_json(FREE_DB).get(str(user_id), 0)

def add_free(user_id):
    data = load_json(FREE_DB)
    data[str(user_id)] = data.get(str(user_id), 0) + 1
    save_json(FREE_DB, data)

def check_trx_payment(txid):
    try:
        url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={txid}"
        r = requests.get(url).json()
        if 'contractRet' not in r or r['contractRet'] != 'SUCCESS':
            return None
        amount = int(r['contractData']['amount']) / 1_000_000
        to_address = r['toAddress']
        if to_address.lower() != WALLET_ADDRESS.lower():
            return None
        if amount >= 20:
            return True
    except:
        pass
    return None

def extract_soundcloud_url(text):
    urls = re.findall(r'(https?://[^\s]+)', text)
    for url in urls:
        if "soundcloud.com" in url:
            if "on.soundcloud.com" in url:
                try:
                    r = requests.get(url, allow_redirects=True)
                    return r.url
                except:
                    return None
            return url
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! 🎵 با /help می‌تونی لیست دستورات رو ببینی.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
🆘 دستورات ربات:
/start - شروع
/help - نمایش دستورات
/buy - عضویت VIP
/verify [TXID] - تایید پرداخت
/approve [user_id] - تایید دستی VIP (فقط ادمین)

🎧 دانلود آهنگ با ارسال لینک SoundCloud
🔓 کاربران رایگان = 3 دانلود
🔐 کاربران VIP = بدون محدودیت (30 روز)
"""
    await update.message.reply_text(msg)

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"""
💳 برای عضویت VIP، مبلغ 20 TRX به آدرس زیر واریز کن:

TRX Wallet:
{WALLET_ADDRESS}

سپس این دستور را ارسال کن:
/verify TXID
"""
    await update.message.reply_text(msg)

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("لطفاً فقط TXID وارد کن.")
        return
    txid = context.args[0]
    user_id = update.effective_user.id
    if check_trx_payment(txid):
        add_vip(user_id)
        await update.message.reply_text("✅ پرداخت تایید شد! عضویت VIP فعال شد.")
    else:
        await update.message.reply_text("❌ تراکنش نامعتبر یا اشتباه بود.")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ فقط ادمین مجازه.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("استفاده صحیح: /approve [user_id]")
        return
    uid = context.args[0]
    add_vip(uid)
    await update.message.reply_text(f"✅ کاربر {uid} به VIP اضافه شد.")
    try:
        await context.bot.send_message(chat_id=int(uid), text="🎉 عضویت VIP شما فعال شد!")
    except:
        pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    url = extract_soundcloud_url(update.message.text)
    if not url:
        await update.message.reply_text("لینک SoundCloud معتبر ارسال کن.")
        return

    if not is_vip(user.id):
        free_count = count_free(user.id)
        if free_count >= 3:
            await update.message.reply_text("🚫 محدودیت 3 دانلود رایگان به پایان رسیده. از /buy برای VIP شدن استفاده کن.")
            return

    await update.message.reply_text("⏳ در حال دانلود...")

    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace(f".{info['ext']}", ".mp3")

        if not os.path.exists(filename):
            await update.message.reply_text("خطا در پردازش فایل.")
            return

        size_mb = os.path.getsize(filename) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            await update.message.reply_text(f"📁 حجم فایل {size_mb:.2f}MB بیشتر از حد مجاز است.")
            os.remove(filename)
            return

        await update.message.reply_audio(audio=open(filename, 'rb'))
        os.remove(filename)

        if not is_vip(user.id):
            add_free(user.id)
            await update.message.reply_text(f"🎁 دانلود رایگان شما ثبت شد ({count_free(user.id)}/3)")

    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")
       
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ فقط ادمین مجازه.")
        return

    vips = load_vips()
    free_users = load_json(FREE_DB)

    msg = "👤 کاربران VIP:\n"
    if vips:
        for uid, exp in vips.items():
            msg += f"🟢 {uid} - اعتبار تا {exp}\n"
    else:
        msg += "هیچ‌کسی نیست!\n"

    msg += "\n👤 کاربران رایگان:\n"
    if free_users:
        for uid, count in free_users.items():
            msg += f"🔵 {uid} - {count}/3 دانلود\n"
    else:
        msg += "هیچ‌کسی نیست!\n"

    await update.message.reply_text(msg)
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("verify", verify))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 ربات فعال شد.")
    app.run_polling()

if __name__ == '__main__':
    main()
