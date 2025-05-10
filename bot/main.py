import os
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    CommandHandler, MessageHandler, filters,
    ConversationHandler
)

# Load token dari .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Buat Konstanta state percakapan
(MENU, INPUT_NOMINAL, INPUT_DESKRIPSI, INPUT_BANK, TANYA_DETAIL, INPUT_BANK_NAME) = range(6)

# File database
DB_FILE = "db.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"banks": {}, "transactions": []}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

user_temp = {}

# Menu
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["➕ Tambah Pemasukan", "➖ Tambah Pengeluaran"],
        ["📅 Rekap Hari Ini", "📆 Rekap Bulanan"],
        ["🏦 Tambah Bank", "💰 Tampilkan Saldo Bank"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("💡 *Sudah boros hari ini? Yuk kelola keuanganmu!* Pilih menu di bawah 👇", reply_markup=reply_markup, parse_mode="Markdown")
    return MENU

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Selamat datang di *Catatan Keuangan Pintar*! Ketik /menu untuk mulai 📊", parse_mode="Markdown")
    return await show_menu(update, context)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_menu(update, context)

async def tambah_transaksi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    tipe = "pemasukan" if "Pemasukan" in text else "pengeluaran"
    user_temp[user_id] = {"tipe": tipe}
    await update.message.reply_text(f"💸 Masukkan nominal *{tipe}* (angka saja):", parse_mode="Markdown")
    return INPUT_NOMINAL

async def input_nominal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        jumlah = int(update.message.text.replace(",", "").replace(".", ""))
        if jumlah <= 0:
            raise ValueError
        user_temp[user_id]["jumlah"] = jumlah
        await update.message.reply_text("📝 Untuk apa/dari mana uang ini?")
        return INPUT_DESKRIPSI
    except ValueError:
        await update.message.reply_text("⚠️ Masukkan nominal yang valid (angka positif).")
        return INPUT_NOMINAL

async def input_deskripsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_temp[user_id]["keterangan"] = update.message.text
    data = load_data()
    banks = list(data["banks"].keys())
    if not banks:
        await update.message.reply_text("🚫 Belum ada bank terdaftar. Tambahkan dulu dengan '🏦 Tambah Bank'")
        return await show_menu(update, context)
    bank_list = "\n".join([f"{i+1}. {b}" for i, b in enumerate(banks)])
    context.user_data["bank_list"] = banks
    await update.message.reply_text(f"🏦 Pilih nomor bank untuk transaksi:\n{bank_list}")
    return INPUT_BANK

async def input_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    banks = context.user_data.get("bank_list", [])
    try:
        idx = int(update.message.text.strip()) - 1
        if idx < 0 or idx >= len(banks):
            raise ValueError
        bank = banks[idx]
    except ValueError:
        await update.message.reply_text("⚠️ Input tidak valid. Masukkan nomor sesuai daftar bank.")
        return INPUT_BANK

    entry = user_temp.pop(user_id)
    entry["tanggal"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry["bank"] = bank

    data["banks"][bank] = data["banks"].get(bank, 0)

    if entry["tipe"] == "pemasukan":
        data["banks"][bank] += entry["jumlah"]
    else:
        data["banks"][bank] -= entry["jumlah"]

    data["transactions"].append(entry)
    save_data(data)

    await update.message.reply_text(
        f"✅ *{entry['tipe'].capitalize()}* sebesar Rp {entry['jumlah']:,} "
        f"untuk '{entry['keterangan']}' dicatat ke bank *{bank}* 💾",
        parse_mode="Markdown"
    )
    return await show_menu(update, context)

async def tambah_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏦 Masukkan nama bank yang ingin ditambahkan:")
    return INPUT_BANK_NAME

async def input_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bank_name = update.message.text.strip()
    if not bank_name or bank_name.lower() == "bank":
        await update.message.reply_text("⚠️ Nama bank tidak valid. Gunakan nama spesifik seperti 'BRI' atau 'BCA'.")
        return INPUT_BANK_NAME

    data = load_data()
    if bank_name in data["banks"]:
        await update.message.reply_text("ℹ️ Bank sudah terdaftar.")
    else:
        data["banks"][bank_name] = 0
        save_data(data)
        await update.message.reply_text(f"✅ Bank *{bank_name}* berhasil ditambahkan! 🏦", parse_mode="Markdown")

    return await show_menu(update, context)

async def rekap_hari_ini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = datetime.now().strftime("%Y-%m-%d")
    pemasukan = pengeluaran = 0
    detail = []

    for tx in data["transactions"]:
        if tx["tanggal"].startswith(today):
            if tx["tipe"] == "pemasukan":
                pemasukan += tx["jumlah"]
            else:
                pengeluaran += tx["jumlah"]
            detail.append(tx)

    total_per_bank = "\n".join([f"- {b}: Rp {saldo:,}" for b, saldo in data["banks"].items()])
    surplus = pemasukan - pengeluaran

    msg = f"💰 *Saldo Bank Saat Ini:*\n{total_per_bank}\n\n"
    msg += f"📅 *Rekap Hari Ini* ({today}):\n"
    msg += f"➕ Pemasukan: Rp {pemasukan:,}\n➖ Pengeluaran: Rp {pengeluaran:,}\n"
    msg += f"{'📈 Surplus' if surplus >= 0 else '📉 Defisit'}: Rp {abs(surplus):,}\n\n"
    msg += "🔍 Mau lihat detail transaksi? (iya/tidak)"

    context.user_data["rekap_detail"] = detail
    await update.message.reply_text(msg, parse_mode="Markdown")
    return TANYA_DETAIL

async def tanya_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "iya":
        detail = context.user_data.get("rekap_detail", [])
        if not detail:
            await update.message.reply_text("📭 Tidak ada transaksi hari ini.")
        else:
            lines = []
            for tx in detail:
                emoji = "➕" if tx["tipe"] == "pemasukan" else "➖"
                line = (
                    f"{emoji} *{tx['tipe'].capitalize()}* Rp {tx['jumlah']:,} - {tx['keterangan']} "
                    f"🏦 {tx['bank']} 📅 {tx['tanggal']}"
                )
                lines.append(line)
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    else:
        await update.message.reply_text("👌 Baik, kembali ke menu.")

    return await show_menu(update, context)

async def rekap_bulanan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    bulan_ini = datetime.now().strftime("%Y-%m")
    pemasukan = pengeluaran = 0

    for tx in data["transactions"]:
        if tx["tanggal"].startswith(bulan_ini):
            if tx["tipe"] == "pemasukan":
                pemasukan += tx["jumlah"]
            else:
                pengeluaran += tx["jumlah"]

    surplus = pemasukan - pengeluaran
    await update.message.reply_text(
        f"📆 *Rekap Bulan Ini* ({bulan_ini}):\n"
        f"➕ Pemasukan: Rp {pemasukan:,}\n➖ Pengeluaran: Rp {pengeluaran:,}\n"
        f"{'📈 Surplus' if surplus >= 0 else '📉 Defisit'}: Rp {abs(surplus):,}",
        parse_mode="Markdown"
    )
    return await show_menu(update, context)

async def tampilkan_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["banks"]:
        await update.message.reply_text("🚫 Belum ada bank terdaftar.")
    else:
        total_per_bank = "\n".join([f"- {b}: Rp {saldo:,}" for b, saldo in data["banks"].items()])
        await update.message.reply_text(f"💰 *Saldo Bank Saat Ini:*\n{total_per_bank}", parse_mode="Markdown")
    return await show_menu(update, context)

# Entry point
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", menu),
            MessageHandler(filters.Regex("^➕ Tambah Pemasukan|➖ Tambah Pengeluaran$"), tambah_transaksi),
            MessageHandler(filters.Regex("^🏦 Tambah Bank$"), tambah_bank),
            MessageHandler(filters.Regex("^📅 Rekap Hari Ini$"), rekap_hari_ini),
            MessageHandler(filters.Regex("^📆 Rekap Bulanan$"), rekap_bulanan),
            MessageHandler(filters.Regex("^💰 Tampilkan Saldo Bank$"), tampilkan_saldo)
        ],
        states={
            MENU: [
                MessageHandler(filters.Regex("^➕ Tambah Pemasukan|➖ Tambah Pengeluaran$"), tambah_transaksi),
                MessageHandler(filters.Regex("^🏦 Tambah Bank$"), tambah_bank),
                MessageHandler(filters.Regex("^📅 Rekap Hari Ini$"), rekap_hari_ini),
                MessageHandler(filters.Regex("^📆 Rekap Bulanan$"), rekap_bulanan),
                MessageHandler(filters.Regex("^💰 Tampilkan Saldo Bank$"), tampilkan_saldo),
            ],
            INPUT_NOMINAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_nominal)],
            INPUT_DESKRIPSI: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_deskripsi)],
            INPUT_BANK: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_bank)],
            TANYA_DETAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, tanya_detail)],
            INPUT_BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_bank_name)],
        },
        fallbacks=[CommandHandler("menu", menu)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    print("🚀 Bot berjalan...")
    app.run_polling()
