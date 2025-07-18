from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import re
import json
import os

DB_FILE = "saved_links.json"

if os.path.exists(DB_FILE):
    with open(DB_FILE, "r") as f:
        saved_links = json.load(f)
else:
    saved_links = {"t.me": [], "chat.whatsapp": []}

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(saved_links, f, indent=2)

def extract_links(text):
    tme_links = re.findall(r"https?://t\.me/\S+", text)
    whatsapp_links = re.findall(r"https?://chat\.whatsapp\.com/\S+", text)
    return tme_links, whatsapp_links

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    tme_links, whatsapp_links = extract_links(text)
    
    new_tme = []
    new_whatsapp = []
    duplicate_count = 0
    
    for link in tme_links:
        if link not in saved_links["t.me"]:
            saved_links["t.me"].append(link)
            new_tme.append(link)
        else:
            duplicate_count += 1
    
    for link in whatsapp_links:
        if link not in saved_links["chat.whatsapp"]:
            saved_links["chat.whatsapp"].append(link)
            new_whatsapp.append(link)
        else:
            duplicate_count += 1
    
    save_db()
    
    reply = ""
    if new_tme or new_whatsapp:
        reply += "✅ روابط جديدة تم حفظها:\n\n"
        if new_tme:
            reply += "📌 روابط تيليجرام:\n"
            for l in new_tme:
                reply += f"- {l}\n"
            reply += "\n"
        if new_whatsapp:
            reply += "📌 روابط واتساب:\n"
            for l in new_whatsapp:
                reply += f"- {l}\n"
            reply += "\n"
    else:
        reply += "⚠️ لم تُضف روابط جديدة، كلها مكررة.\n\n"
    
    if duplicate_count > 0:
        reply += f"⚠️ تم تجاهل {duplicate_count} رابط مكرر."
    
    await update.message.reply_text(reply)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبًا! أرسل لي رسالة تحتوي على روابط تيليجرام أو واتساب، وسأخزنها لك مع حذف المكرر.")

if __name__ == "__main__":
    TOKEN = os.getenv("TOKEN")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("البوت يعمل الآن...")
    app.run_polling()