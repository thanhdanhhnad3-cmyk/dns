#!/usr/bin/env python3
"""
Simple Telegram Bot for NextDNS Auto-Register Tool
"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from datetime import datetime
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, filters, CallbackQueryHandler

# Read .env file if present
def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value

load_dotenv()

# Import main functions
from main import register_single
from tinyhost import TinyhostClient

# Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OUTPUT_FILE = "api_keys.txt"
PROFILE_LINKS_FILE = "profile_links.txt"

# Create a shared tinyhost client
tinyhost_client = TinyhostClient()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    await update.message.reply_text(
        "🤖 *NextDNS Auto-Register Bot*\n\n"
        "Lệnh dostupné:\n"
        "/generate - Tạo API key mới\n"
        "/list - Xem danh sách API keys\n"
        "/help - Hướng dẫn sử dụng",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    await update.message.reply_text(
        "📖 *Hướng Dẫn Sử Dụng*\n\n"
        "1️⃣ *Tạo API Key Mới*\n"
        "Nhập: /generate\n"
        "Chương trình sẽ tạo 1 tài khoản NextDNS mới\n\n"
        "2️⃣ *Xem Danh Sách*\n"
        "Nhập: /list\n"
        "Xem các API keys đã tạo\n\n"
        "⏱️ Chú ý: Mỗi lần tạo mất khoảng 30-40 giây",
        parse_mode="Markdown"
    )


async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /generate command"""
    user_id = update.effective_user.id
    
    # Send "creating..." message
    msg = await update.message.reply_text("⏳ Đang tạo account NextDNS...")
    
    try:
        # Register account
        result = await register_single(tinyhost_client, visible=False)
        
        if result and result.success and result.api_key:
            profile_link = (
                f"https://apple.nextdns.io/?profile={result.profile_id}"
                if result.profile_id else "N/A"
            )
            password_text = f"🔒 Mật khẩu: `{result.password}`\n" if result.password else ""
            # Format response
            response = (
                f"✅ *Tạo Thành Công!*\n\n"
                f"📧 Email: `{result.email}`\n"
                f"{password_text}"
                f"🔑 API Key: `{result.api_key}`\n"
                f"📱 Profile ID: `{result.profile_id}`\n"
                f"🔗 Link: {profile_link}\n"
                f"⏰ Tạo lúc: {result.created_at}"
            )
            await msg.edit_text(response, parse_mode="Markdown")
        else:
            await msg.edit_text("❌ Tạo thất bại. Vui lòng thử lại!")
            
    except Exception as e:
        await msg.edit_text(f"❌ Lỗi: {str(e)}")


async def list_keys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list command"""
    try:
        if not os.path.exists(PROFILE_LINKS_FILE):
            await update.message.reply_text("📭 Chưa có API keys nào")
            return
        
        with open(PROFILE_LINKS_FILE, "r") as f:
            lines = f.readlines()
        
        if not lines:
            await update.message.reply_text("📭 Chưa có API keys nào")
            return
        
        # Show last 5 API keys
        message = "📋 *Danh Sách API Keys* (5 gần đây)\n\n"
        for i, line in enumerate(reversed(lines[-5:]), 1):
            parts = line.strip().split("|")
            if len(parts) >= 2:
                link = parts[0]
                api_key = parts[1][:16] + "..."
                message += f"{i}. 🔗 {link}\n   🔑 {api_key}\n\n"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")


def find_api_key_for_profile(profile_id: str) -> str | None:
    """Look up api_key from PROFILE_LINKS_FILE by profile_id."""
    if not os.path.exists(PROFILE_LINKS_FILE):
        return None
    try:
        with open(PROFILE_LINKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if not parts:
                    continue
                link = parts[0]
                api_key = parts[1] if len(parts) > 1 else None
                if profile_id in link and api_key:
                    return api_key
    except Exception:
        return None
    return None


async def handle_message_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect NextDNS profile links in incoming messages and ask for confirmation."""
    text = update.message.text or ""
    # find pattern like ?profile=PROFILE_ID
    import re
    m = re.search(r"[?&]profile=([a-zA-Z0-9_-]{6,})", text)
    if not m:
        return
    profile_id = m.group(1)

    keyboard = [
        [InlineKeyboardButton("✅ Xác nhận gỡ revenuecat", callback_data=f"unblock:{profile_id}"),
         InlineKeyboardButton("❌ Hủy", callback_data=f"cancel_unblock:{profile_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Phát hiện profile `{profile_id}`. Gỡ `api.revenuecat.com` khỏi denylist?",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def callback_unblock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith("cancel_unblock:"):
        await query.edit_message_text("❌ Đã hủy")
        return

    if not data.startswith("unblock:"):
        await query.edit_message_text("❌ Dữ liệu không hợp lệ")
        return

    profile_id = data.split(":", 1)[1]

    # Find api_key for profile
    api_key = find_api_key_for_profile(profile_id)
    if not api_key:
        await query.edit_message_text("❌ Không tìm thấy API key cho profile này. Vui lòng thêm API key vào `profile_links.txt`.")
        return

    domain = "api.revenuecat.com"
    # Call NextDNS API to remove domain from denylist
    try:
        url = f"https://api.nextdns.io/profiles/{profile_id}/denylist/{domain}"
        headers = {"X-Api-Key": api_key}
        resp = requests.delete(url, headers=headers, timeout=15)
        if resp.status_code in (200, 204):
            await query.edit_message_text(f"✅ Đã gỡ `{domain}` khỏi denylist của profile {profile_id}")
        else:
            await query.edit_message_text(f"❌ Gỡ thất bại ({resp.status_code}): {resp.text}")
    except Exception as e:
        await query.edit_message_text(f"❌ Lỗi khi gọi API: {e}")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()


def run_health_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


def keep_alive_loop_blocking():
    """
    Blocking keep-alive loop for thread-safe operation.
    Pings the health endpoint every 5 minutes using requests and time.sleep.
    This avoids creating a separate asyncio event loop in a thread.
    """
    import time
    while True:
        try:
            time.sleep(300)  # 5 minutes
            try:
                response = requests.get("http://localhost:8080/healthz", timeout=5)
                if response.status_code == 200:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] 🔄 Keep-alive ping OK")
            except Exception as e:
                print(f"Keep-alive ping failed: {e}")
        except Exception as e:
            print(f"Error in keep-alive loop: {e}")
            try:
                time.sleep(60)
            except Exception:
                break


def main() -> None:
    """Start the bot"""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Lỗi: Vui lòng set TELEGRAM_BOT_TOKEN")
        print("Cách set: export TELEGRAM_BOT_TOKEN='your_token_here'")
        return

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("generate", generate))
    application.add_handler(CommandHandler("list", list_keys))
    # Message handler to detect profile links
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_links))
    # Callback query handler for unblock/cancel
    application.add_handler(CallbackQueryHandler(callback_unblock_handler))

    # Start lightweight health server in background
    # Use Render-provided PORT if available
    try:
        port_env = int(os.getenv("PORT", "8080"))
    except Exception:
        port_env = 8080
    health_thread = threading.Thread(target=lambda: run_health_server(port_env), daemon=True)
    health_thread.start()

    # Start keep-alive thread (blocking loop, no asyncio event loop created)
    keep_alive_thread = threading.Thread(
        target=keep_alive_loop_blocking,
        daemon=True,
    )
    keep_alive_thread.start()

    print("🤖 Bot đang chạy...")
    print(f"Token: {TELEGRAM_BOT_TOKEN[:10]}...")
    print("🌐 Health check: http://0.0.0.0:8080/healthz")
    print("💪 Keep-alive: Bật (ping mỗi 5 phút)")

    application.run_polling()


if __name__ == "__main__":
    main()
