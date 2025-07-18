from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import re
import json
import os
from urllib.parse import urlparse

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

def normalize_link(link):
    parsed = urlparse(link)
    # حذف / من النهاية + حذف query params إن وجدت
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if user is in link verification mode
    if await handle_link_verification(update, context):
        return
    
    text = update.message.text
    tme_links_raw, whatsapp_links_raw = extract_links(text)
    
    # Normalize all
    tme_links = [normalize_link(link) for link in tme_links_raw]
    whatsapp_links = [normalize_link(link) for link in whatsapp_links_raw]

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
            reply += "📌 روابط تيليجرام:\n" + "\n".join(f"- {l}" for l in new_tme) + "\n\n"
        if new_whatsapp:
            reply += "📌 روابط واتساب:\n" + "\n".join(f"- {l}" for l in new_whatsapp) + "\n\n"
    else:
        reply += "⚠️ لم تُضف روابط جديدة، كلها مكررة.\n"

    if duplicate_count:
        reply += f"🔁 تم تجاهل {duplicate_count} رابط مكرر."

    await update.message.reply_text(reply)

async def show_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not saved_links["t.me"] and not saved_links["chat.whatsapp"]:
        await update.message.reply_text("📂 لا يوجد روابط مخزنة حالياً.")
        return

    # Send summary first
    total_tme = len(saved_links["t.me"])
    total_whatsapp = len(saved_links["chat.whatsapp"])
    summary = f"📁 ملخص الروابط المخزنة:\n"
    summary += f"📌 تيليجرام: {total_tme} رابط\n"
    summary += f"📌 واتساب: {total_whatsapp} رابط\n\n"
    summary += "سيتم إرسال الروابط على دفعات..."
    
    await update.message.reply_text(summary)

    # Send Telegram links in chunks
    if saved_links["t.me"]:
        await update.message.reply_text("📌 روابط تيليجرام:")
        chunk_size = 20
        for i in range(0, len(saved_links["t.me"]), chunk_size):
            chunk = saved_links["t.me"][i:i+chunk_size]
            reply = f"الجزء {i//chunk_size + 1}:\n" + "\n".join(f"- {link}" for link in chunk)
            await update.message.reply_text(reply)

    # Send WhatsApp links in chunks
    if saved_links["chat.whatsapp"]:
        await update.message.reply_text("📌 روابط واتساب:")
        chunk_size = 20
        for i in range(0, len(saved_links["chat.whatsapp"]), chunk_size):
            chunk = saved_links["chat.whatsapp"][i:i+chunk_size]
            reply = f"الجزء {i//chunk_size + 1}:\n" + "\n".join(f"- {link}" for link in chunk)
            await update.message.reply_text(reply)

async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not saved_links["t.me"] and not saved_links["chat.whatsapp"]:
        await update.message.reply_text("📂 لا يوجد روابط مخزنة للفحص.")
        return
    
    await update.message.reply_text("🔍 سأبدأ بفحص الروابط المخزنة...\nاضغط على الأزرار للتحكم في الروابط.")
    
    # Store user state for link checking
    user_id = update.effective_user.id
    context.user_data['checking_links'] = True
    context.user_data['current_links'] = []
    context.user_data['current_index'] = 0
    context.user_data['links_to_delete'] = []
    
    # Combine all links with their types (limit to 10 for testing)
    all_links = []
    for link in saved_links["t.me"][:5]:  # First 5 Telegram links
        all_links.append(("t.me", link))
    for link in saved_links["chat.whatsapp"][:5]:  # First 5 WhatsApp links
        all_links.append(("chat.whatsapp", link))
    
    context.user_data['current_links'] = all_links
    
    if all_links:
        await send_link_check_message(update, context, 0)

async def send_link_check_message(update_or_query, context: ContextTypes.DEFAULT_TYPE, index: int):
    current_links = context.user_data['current_links']
    link_type, link_url = current_links[index]
    platform_name = "تيليجرام" if link_type == "t.me" else "واتساب"
    
    # Create inline keyboard
    keyboard = [
        [
            InlineKeyboardButton("✅ يعمل", callback_data="link_works"),
            InlineKeyboardButton("❌ لا يعمل", callback_data="link_broken")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = f"📍 الرابط {index + 1}/{len(current_links)}\n🔗 {link_url}\n📱 منصة: {platform_name}\n\nهل هذا الرابط يعمل؟"
    
    if hasattr(update_or_query, 'edit_message_text'):  # It's a callback query
        await update_or_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:  # It's an update from message
        await update_or_query.message.reply_text(message_text, reply_markup=reply_markup)

async def handle_link_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not context.user_data.get('checking_links', False):
        return
    
    current_links = context.user_data['current_links']
    current_index = context.user_data['current_index']
    
    if query.data == "link_broken":
        # Mark link for deletion
        link_type, link_url = current_links[current_index]
        context.user_data['links_to_delete'].append((link_type, link_url))
    
    # Move to next link
    current_index += 1
    context.user_data['current_index'] = current_index
    
    if current_index < len(current_links):
        await send_link_check_message(query, context, current_index)
    else:
        # Finished checking all links
        links_to_delete = context.user_data['links_to_delete']
        
        if links_to_delete:
            # Delete non-working links
            deleted_count = 0
            for link_type, link_url in links_to_delete:
                if link_url in saved_links[link_type]:
                    saved_links[link_type].remove(link_url)
                    deleted_count += 1
            
            save_db()
            await query.edit_message_text(f"🗑️ تم حذف {deleted_count} رابط غير فعال.\n✅ تم الانتهاء من فحص الروابط!")
        else:
            await query.edit_message_text("✅ جميع الروابط تعمل بشكل جيد!\n✅ تم الانتهاء من فحص الروابط!")
        
        # Clear user state
        context.user_data.clear()

async def handle_link_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This function is no longer needed as we use callback handlers
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أرسل روابط تيليجرام أو واتساب وسأخزنها بدون تكرار.\n\n🔍 استخدم /check لفحص الروابط المخزنة وحذف غير الفعالة.")

# 🔐 التوكن من متغيرات البيئة
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ لم يتم العثور على التوكن! تأكد من إضافة TOKEN في الـ Secrets")
    exit()

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("show", show_links))
    app.add_handler(CommandHandler("check", check_links))
    app.add_handler(CallbackQueryHandler(handle_link_verification_callback, pattern="^link_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ البوت شغال... انتظر الرسائل")
    app.run_polling()