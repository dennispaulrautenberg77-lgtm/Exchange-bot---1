#!/usr/bin/env python3
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
from config import BOT_TOKEN, ADMIN_ID, ADMIN_IDS, FEES, IBAN, INHABER, CHANNEL_ID

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

(STATE_MENU, STATE_SELECT_METHOD, STATE_ENTER_AMOUNT,
 STATE_ENTER_LTC_ADDRESS, STATE_CONFIRM_ORDER, STATE_RATING, STATE_SAVE_ADDRESS) = range(7)

def calc_payout(amount, method):
    return round(amount * (1 - FEES.get(method, 0.5)), 2)

def method_label(method):
    return {"echtzeit": "⚡ Echtzeit Transfer", "sepa": "🏦 SEPA Überweisung", "paypal": "💙 PayPal F&F"}.get(method, method)

def stars(n):
    return "⭐" * n + "☆" * (5 - n)

async def start(update, ctx):
    user = update.effective_user
    welcome = (
        "┌─────────────────────────────────┐\n"
        "│   💎  UNCLEAN EXCHANGE  💎       │\n"
        "│   Premium Crypto Exchange        │\n"
        "└─────────────────────────────────┘\n\n"
        f"Willkommen, *{user.first_name}* 👋\n\n"
        "Wir tauschen dein Geld diskret & schnell in *Litecoin (LTC)* um.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 *Verfügbare Methoden:*\n\n"
        f"  ⚡ Echtzeit Transfer  →  *{int(FEES['echtzeit']*100)}% Gebühr*\n"
        f"  🏦 SEPA Überweisung  →  *{int(FEES['sepa']*100)}% Gebühr*\n"
        f"  💙 PayPal F&F            →  *{int(FEES['paypal']*100)}% Gebühr*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔒 *100% diskret · Schnelle Abwicklung*\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    keyboard = [
        [InlineKeyboardButton("💱 Exchange starten", callback_data="start_exchange")],
        [InlineKeyboardButton("📋 Meine LTC Adresse", callback_data="my_address")],
        [InlineKeyboardButton("ℹ️ Über uns", callback_data="about")],
    ]
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_MENU

async def menu_handler(update, ctx):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "start_exchange":
        return await ask_method(update, ctx)
    elif data == "my_address":
        saved = ctx.user_data.get("ltc_address")
        if saved:
            text = f"📋 *Gespeicherte LTC Adresse:*\n\n`{saved}`\n\nMöchtest du die Adresse ändern?"
            keyboard = [
                [InlineKeyboardButton("✏️ Adresse ändern", callback_data="change_address")],
                [InlineKeyboardButton("🏠 Hauptmenü", callback_data="main_menu")],
            ]
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                          reply_markup=InlineKeyboardMarkup(keyboard))
            return STATE_MENU
        else:
            await query.edit_message_text(
                "📋 *LTC Adresse speichern*\n\nDu hast noch keine Adresse gespeichert.\nSende mir deine Litecoin Adresse:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="main_menu")]]))
            return STATE_SAVE_ADDRESS
    elif data == "change_address":
        await query.edit_message_text(
            "✏️ *Neue LTC Adresse eingeben:*\n\nBitte sende deine neue Litecoin Adresse.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="main_menu")]]))
        return STATE_SAVE_ADDRESS
    elif data == "about":
        text = (
            "━━━━━━━━━━━━━━━━━━━━━━\n💎 *UNCLEAN EXCHANGE*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔒 Diskrete & sichere Abwicklung\n⚡ Schnelle Bearbeitung\n💎 Premium Service\n🌍 24/7 erreichbar\n\n"
            f"📊 *Unsere Gebühren:*\n  • Echtzeit: {int(FEES['echtzeit']*100)}%\n"
            f"  • SEPA: {int(FEES['sepa']*100)}%\n  • PayPal F&F: {int(FEES['paypal']*100)}%\n\n"
            "📤 *Auszahlung:* Litecoin (LTC)\n━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Hauptmenü", callback_data="main_menu")]]))
        return STATE_MENU
    elif data == "main_menu":
        return await back_to_main(update, ctx)
    return STATE_MENU

async def save_address_handler(update, ctx):
    address = update.message.text.strip()
    if not (address.startswith(("L", "M", "ltc1")) and len(address) >= 26):
        await update.message.reply_text("❌ *Ungültige LTC Adresse!*\n\nBitte gib eine gültige Litecoin Adresse ein.",
                                        parse_mode=ParseMode.MARKDOWN)
        return STATE_SAVE_ADDRESS
    ctx.user_data["ltc_address"] = address
    await update.message.reply_text(
        f"✅ *Adresse gespeichert!*\n\n`{address}`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💱 Exchange starten", callback_data="start_exchange")],
            [InlineKeyboardButton("🏠 Hauptmenü", callback_data="main_menu")],
        ]))
    return STATE_MENU

async def ask_method(update, ctx):
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n💱 *EXCHANGE STARTEN*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Wähle deine *Zahlungsmethode:*\n"
    )
    keyboard = [
        [InlineKeyboardButton(f"⚡ Echtzeit Transfer  ({int(FEES['echtzeit']*100)}% Gebühr)", callback_data="method_echtzeit")],
        [InlineKeyboardButton(f"🏦 SEPA Überweisung  ({int(FEES['sepa']*100)}% Gebühr)", callback_data="method_sepa")],
        [InlineKeyboardButton(f"💙 PayPal F&F             ({int(FEES['paypal']*100)}% Gebühr)", callback_data="method_paypal")],
        [InlineKeyboardButton("❌ Abbrechen", callback_data="main_menu")],
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_SELECT_METHOD

async def method_selected(update, ctx):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("method_", "")
    ctx.user_data["method"] = method
    text = (
        f"✅ *{method_label(method)}* gewählt\n📊 Gebühr: *{int(FEES[method]*100)}%*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n💶 *Betrag eingeben*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Wie viel Euro möchtest du tauschen?\n\n_Beispiel: 500_"
    )
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abbrechen", callback_data="main_menu")]]))
    return STATE_ENTER_AMOUNT

async def amount_entered(update, ctx):
    try:
        amount = float(update.message.text.strip().replace(",", ".").replace("€", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ *Ungültiger Betrag!*\n\n_Beispiel: 500_", parse_mode=ParseMode.MARKDOWN)
        return STATE_ENTER_AMOUNT

    method = ctx.user_data["method"]
    payout = calc_payout(amount, method)
    ctx.user_data["amount"] = amount
    ctx.user_data["payout_eur"] = payout

    saved_address = ctx.user_data.get("ltc_address")
    keyboard_rows = []
    if saved_address:
        keyboard_rows.append([InlineKeyboardButton("✅ Gespeicherte Adresse verwenden", callback_data="use_saved_address")])
    keyboard_rows.append([InlineKeyboardButton("❌ Abbrechen", callback_data="main_menu")])

    text = (
        f"💶 Betrag: *{amount:.2f} €*\n"
        f"📊 Gebühr ({int(FEES[method]*100)}%): *{amount - payout:.2f} €*\n"
        f"💎 Du erhältst: *≈ {payout:.2f} € in LTC*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n📤 *LTC Auszahlungsadresse*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Sende mir deine *Litecoin Adresse:*"
    )
    if saved_address:
        text += f"\n\n_Gespeichert: `{saved_address}`_"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=InlineKeyboardMarkup(keyboard_rows))
    return STATE_ENTER_LTC_ADDRESS

async def use_saved_address(update, ctx):
    query = update.callback_query
    await query.answer()
    ctx.user_data["ltc_address_order"] = ctx.user_data.get("ltc_address")
    return await show_confirmation(update, ctx)

async def ltc_address_entered(update, ctx):
    address = update.message.text.strip()
    if not (address.startswith(("L", "M", "ltc1")) and len(address) >= 26):
        await update.message.reply_text("❌ *Ungültige LTC Adresse!*", parse_mode=ParseMode.MARKDOWN)
        return STATE_ENTER_LTC_ADDRESS
    ctx.user_data["ltc_address_order"] = address
    keyboard = [
        [InlineKeyboardButton("💾 Adresse speichern", callback_data="save_for_later")],
        [InlineKeyboardButton("➡️ Weiter", callback_data="skip_save")],
    ]
    await update.message.reply_text(
        f"✅ Adresse: `{address}`\n\nMöchtest du diese für spätere Transaktionen speichern?",
        parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_CONFIRM_ORDER

async def save_and_continue(update, ctx):
    query = update.callback_query
    await query.answer()
    if query.data == "save_for_later":
        ctx.user_data["ltc_address"] = ctx.user_data.get("ltc_address_order")
    return await show_confirmation(update, ctx)

async def show_confirmation(update, ctx):
    d = ctx.user_data
    method = d["method"]
    amount = d["amount"]
    payout = d["payout_eur"]
    address = d["ltc_address_order"]
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n📋 *AUFTRAGSÜBERSICHT*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 Methode:         *{method_label(method)}*\n"
        f"💶 Betrag:            *{amount:.2f} €*\n"
        f"📊 Gebühr ({int(FEES[method]*100)}%):  *{amount - payout:.2f} €*\n"
        f"💎 Auszahlung:    *≈ {payout:.2f} € in LTC*\n\n"
        f"📤 LTC Adresse:\n`{address}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n⚠️ *Bitte überprüfe alle Angaben!*"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Auftrag absenden", callback_data="confirm_order")],
        [InlineKeyboardButton("❌ Abbrechen", callback_data="main_menu")],
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_CONFIRM_ORDER

async def confirm_order(update, ctx):
    query = update.callback_query
    await query.answer()
    d = ctx.user_data
    user = update.effective_user
    method = d["method"]
    amount = d["amount"]
    payout = d["payout_eur"]
    address = d["ltc_address_order"]
    order_id = f"UE{user.id}{int(amount*100)}"

    admin_text = (
        "🔔 *NEUE EXCHANGE ANFRAGE*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Order ID: `{order_id}`\n"
        f"👤 User: [{user.first_name}](tg://user?id={user.id}) (`{user.id}`)\n"
        f"🕐 Username: @{user.username or 'N/A'}\n\n"
        f"💳 Methode: *{method_label(method)}*\n"
        f"💶 Betrag: *{amount:.2f} €*\n"
        f"📊 Gebühr ({int(FEES[method]*100)}%): *{amount - payout:.2f} €*\n"
        f"💎 Auszahlung: *≈ {payout:.2f} € in LTC*\n\n"
        f"📤 LTC Adresse:\n`{address}`\n\n━━━━━━━━━━━━━━━━━━━━━━"
    )
    admin_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Annehmen", callback_data=f"admin_accept_{user.id}_{order_id}"),
        InlineKeyboardButton("❌ Ablehnen", callback_data=f"admin_reject_{user.id}_{order_id}"),
    ]])

    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_message(aid, admin_text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=admin_keyboard)
        except Exception as e:
            logger.error(f"Admin notification failed for {aid}: {e}")

    try:
        await ctx.bot.send_message(CHANNEL_ID, admin_text, parse_mode=ParseMode.MARKDOWN,
                                   reply_markup=admin_keyboard)
    except Exception as e:
        logger.error(f"Channel notification failed: {e}")

    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n✅ *AUFTRAG EINGEGANGEN!*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 Deine Order ID: `{order_id}`\n\n"
        "Dein Auftrag wurde übermittelt.\nDer Admin meldet sich schnellstmöglich.\n\n"
        "⏳ *Bitte warte auf die Bestätigung.*\n\n━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Bot bewerten", callback_data="rate_bot")],
            [InlineKeyboardButton("🏠 Hauptmenü", callback_data="main_menu")],
        ]))
    return STATE_MENU

async def rate_bot(update, ctx):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⭐ 1", callback_data="rate_1"),
         InlineKeyboardButton("⭐ 2", callback_data="rate_2"),
         InlineKeyboardButton("⭐ 3", callback_data="rate_3")],
        [InlineKeyboardButton("⭐ 4", callback_data="rate_4"),
         InlineKeyboardButton("⭐ 5", callback_data="rate_5")],
        [InlineKeyboardButton("🏠 Hauptmenü", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "⭐ *Bot bewerten*\n\nWie zufrieden bist du mit unserem Service?\n\nWähle deine Bewertung:",
        parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_RATING

async def rating_received(update, ctx):
    query = update.callback_query
    await query.answer()
    rating = int(query.data.replace("rate_", ""))
    user = update.effective_user
    try:
        await ctx.bot.send_message(ADMIN_ID,
            f"⭐ *Neue Bewertung*\n\n👤 User: [{user.first_name}](tg://user?id={user.id})\n"
            f"Bewertung: {stars(rating)} ({rating}/5)", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass
    responses = {1: "😔 Danke! Wir arbeiten daran, besser zu werden.",
                 2: "😐 Danke! Wir nehmen dein Feedback ernst.",
                 3: "🙂 Danke für deine Bewertung!",
                 4: "😊 Super! Danke für dein positives Feedback!",
                 5: "🤩 Wow, 5 Sterne! Vielen Dank!"}
    await query.edit_message_text(
        f"✅ *Bewertung gespeichert!*\n\n{stars(rating)} ({rating}/5)\n\n{responses[rating]}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Hauptmenü", callback_data="main_menu")]]))
    return STATE_MENU

async def admin_decision(update, ctx):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("⛔ Kein Zugriff!", show_alert=True)
        return
    parts = query.data.split("_")
    action = parts[1]
    user_id = int(parts[2])
    order_id = parts[3]
    if action == "accept":
        user_msg = (
            "━━━━━━━━━━━━━━━━━━━━━━\n✅ *AUFTRAG ANGENOMMEN!*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 Order ID: `{order_id}`\n\n"
            "Dein Auftrag wurde *angenommen*.\n"
            "Bitte überweise den Betrag an folgende Bankdaten:\n\n"
            "🏦 *Zahlungsempfänger:*\n"
            f"`{INHABER}`\n\n"
            f"💳 *IBAN:*\n`{IBAN}`\n\n"
            "💎 *Nach Zahlungseingang wird LTC sofort überwiesen!*\n━━━━━━━━━━━━━━━━━━━━━━"
        )
        confirm = f"✅ Auftrag `{order_id}` angenommen & User benachrichtigt."
    else:
        user_msg = (
            "━━━━━━━━━━━━━━━━━━━━━━\n❌ *AUFTRAG ABGELEHNT*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 Order ID: `{order_id}`\n\nDein Auftrag wurde *abgelehnt*.\n"
            "Bitte kontaktiere den Support.\n━━━━━━━━━━━━━━━━━━━━━━"
        )
        confirm = f"❌ Auftrag `{order_id}` abgelehnt & User benachrichtigt."
    try:
        await ctx.bot.send_message(user_id, user_msg, parse_mode=ParseMode.MARKDOWN,
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Hauptmenü", callback_data="main_menu")]]))
    except Exception as e:
        logger.error(f"Could not notify user {user_id}: {e}")
    await query.edit_message_text(query.message.text + f"\n\n{confirm}", parse_mode=ParseMode.MARKDOWN)

async def back_to_main(update, ctx):
    query = update.callback_query
    if query:
        await query.answer()
    user = query.from_user if query else update.effective_user
    keyboard = [
        [InlineKeyboardButton("💱 Exchange starten", callback_data="start_exchange")],
        [InlineKeyboardButton("📋 Meine LTC Adresse", callback_data="my_address")],
        [InlineKeyboardButton("ℹ️ Über uns", callback_data="about")],
    ]
    text = (
        "┌─────────────────────────────────┐\n"
        "│   💎  UNCLEAN EXCHANGE  💎       │\n"
        "│   Premium Crypto Exchange        │\n"
        "└─────────────────────────────────┘\n\n"
        f"Hey *{user.first_name}*, was möchtest du tun?\n\n━━━━━━━━━━━━━━━━━━━━━━"
    )
    if query:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_MENU

async def cancel(update, ctx):
    await update.message.reply_text("❌ Abgebrochen. /start zum Neustart.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def keep_alive():
    server = HTTPServer(("0.0.0.0", 5000), KeepAliveHandler)
    server.serve_forever()

def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    logger.info("🌐 Keepalive-Server gestartet auf Port 5000")
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STATE_MENU: [
                CallbackQueryHandler(menu_handler, pattern="^(start_exchange|my_address|about|main_menu|change_address)$"),
                CallbackQueryHandler(rate_bot, pattern="^rate_bot$"),
                CallbackQueryHandler(rating_received, pattern="^rate_[1-5]$"),
            ],
            STATE_SELECT_METHOD: [
                CallbackQueryHandler(method_selected, pattern="^method_"),
                CallbackQueryHandler(back_to_main, pattern="^main_menu$"),
            ],
            STATE_ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, amount_entered),
                CallbackQueryHandler(back_to_main, pattern="^main_menu$"),
            ],
            STATE_ENTER_LTC_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ltc_address_entered),
                CallbackQueryHandler(use_saved_address, pattern="^use_saved_address$"),
                CallbackQueryHandler(back_to_main, pattern="^main_menu$"),
            ],
            STATE_CONFIRM_ORDER: [
                CallbackQueryHandler(save_and_continue, pattern="^(save_for_later|skip_save)$"),
                CallbackQueryHandler(confirm_order, pattern="^confirm_order$"),
                CallbackQueryHandler(back_to_main, pattern="^main_menu$"),
            ],
            STATE_RATING: [
                CallbackQueryHandler(rating_received, pattern="^rate_[1-5]$"),
                CallbackQueryHandler(back_to_main, pattern="^main_menu$"),
            ],
            STATE_SAVE_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_address_handler),
                CallbackQueryHandler(back_to_main, pattern="^main_menu$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_decision, pattern="^admin_(accept|reject)_"))
    logger.info("💎 Unclean Exchange Bot gestartet!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
