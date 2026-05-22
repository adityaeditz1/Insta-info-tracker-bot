import requests
import html
import asyncio
import os
import time
import sqlite3
import asyncpg
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.error import Forbidden, BadRequest
ADMIN_ID = 1721427995
# Force Subscribe Configuration
FORCE_CHANNEL_USERNAME = "@aditya_labs"
FORCE_CHANNEL_ID = -1003644491983
APIFY_TOKEN = "apify_api_CwA9rgrlRJPlipheKCHhwTVVh3YfiS3cHMra"
VERIFY_URL = "https://tj4arqo.short.gy/ig-verify"
VERIFY_DURATION = 24 * 60 * 60
DATABASE_URL = "postgresql://postgres.epluuuabtkbknekreeqv:SMARTCHHOTU2006@aws-1-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require"
db_pool = None
BOT_ID = 7

conn = sqlite3.connect("verified_users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS verified_users (
    user_id INTEGER PRIMARY KEY,
    verified_at INTEGER
)
""")
conn.commit()

# ================= VERIFICATION CORE =================
def is_verified(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True

    cursor.execute(
        "SELECT verified_at FROM verified_users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()

    if not row:
        return False

    return (time.time() - row[0]) < VERIFY_DURATION


def mark_verified(user_id: int):
    cursor.execute(
        "REPLACE INTO verified_users (user_id, verified_at) VALUES (?, ?)",
        (user_id, int(time.time()))
    )
    conn.commit()

# ================= /start (VERIFY ONLY) =================
async def ensure_verified(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    if not is_verified(user.id):
        buttons = [
            [InlineKeyboardButton("👉 Click to Verify", url=VERIFY_URL)],
            [InlineKeyboardButton("❓ How to Verify", url="https://t.me/+SReToBAyE9MwNjUx")]
        ]

        await update.message.reply_text(
            "🔒 <b>Access Restricted</b>\n\n"
            "<b>To use this bot, please complete verification below.</b>\n\n"
            "<b>After verification, click I've Verified.</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return False

    return True

async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = await context.bot.get_chat_member(
            chat_id=FORCE_CHANNEL_ID,
            user_id=user_id
        )
        return member.status in ["member", "administrator", "creator"]
    except:
        # ❌ Error aaye to NOT JOINED maanenge
        return False

async def force_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if await check_membership(user.id, context):
        return True

    buttons = [
        [InlineKeyboardButton(
            "🔔 Join Channel",
            url="https://t.me/aditya_labs"
        )],
        [InlineKeyboardButton(
            "✅ I've Joined",
            callback_data="check_subscription"
        )]
    ]

    text = (
        "🔒 <b>Access Restricted</b>\n\n"
        "Please join our official channel to use this bot."
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )

    return False

async def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    # 1️⃣ ALWAYS channel check first
    if not await check_membership(update.effective_user.id, context):
        await force_verify(update, context)
        return False

    # 2️⃣ THEN verify check
    if not await ensure_verified(update, context):
        return False

    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    await save_user(user)

    # ✅ VERIFY VIA LANDING PAGE REDIRECT
    if context.args and context.args[0] == "verify":
        mark_verified(user_id)

        await update.message.reply_text(
            "✅ <b>Verified!</b>\n\n"
            "<b>You can now use this bot.</b>\n"
            "<b>Access is valid for 24 hours.</b>",
            parse_mode="HTML"
        )
        return

   # 🔒 Channel join check ONLY on /start
    if not await force_verify(update, context):
        return

    msg = """
🔥⚡ <b>WELCOME TO INSTAGRAM INFO BOT</b>

🔍 <b>Get instant Instagram user details</b>
❤️ <b>Followers • Following • Posts</b>
✅ <b>Public / Private status</b>
❌ <b>No login required</b>

🚀 <b>How to use:</b>
<code>/info username</code>
<code>/info @username</code>

💎 <b>Fast • Clean • Accurate</b>

━━━━━━━━━━━━━━━
🤖 <b>Powered by @aditya_labs</b>
"""
    await update.message.reply_text(msg, parse_mode="HTML")

async def save_user(user):
    async with db_pool.acquire() as conn:

        # users table
        await conn.execute(
        """
        INSERT INTO users (user_id, username, first_name, blocked)
        VALUES ($1, $2, $3, FALSE)
        ON CONFLICT (user_id)
        DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, blocked = FALSE, last_active = now()
        """,
            user.id,
            user.username,
            user.first_name
        )

        # user_bot_map table
        await conn.execute(
        """
            INSERT INTO user_bot_map (user_id, bot_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            user.id,
            BOT_ID
        )

# ================= /admin PANEL =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    buttons = [
        [
            InlineKeyboardButton("📊 Statistics", callback_data="stats"),
            InlineKeyboardButton("📣 Broadcast", callback_data="broadcast")
        ]
    ]

    await update.message.reply_text(
        "🛠️ **Admin Panel**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

# ================= CALLBACK ROUTER =================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # ================= VERIFY BUTTON =================
    if data == "check_subscription":
        user_joined = await check_membership(user_id, context)

        # ---------- NOT JOINED ----------
        if not user_joined:
            await query.answer("❌ You haven't joined yet!", show_alert=True)

            failed_msg = await query.message.reply_text(
                "❌ <b>Verification Failed!</b>\n\n"
                "Please join the channel and try again.",
                parse_mode="HTML"
            )

            # store ALL failed message ids
            failed_ids = context.user_data.get("failed_verify_msg_ids", [])
            failed_ids.append(failed_msg.message_id)
            context.user_data["failed_verify_msg_ids"] = failed_ids
            return

        # ---------- JOINED ----------
        await query.answer("✅ Verified!")

        # delete verify button message
        try:
            await query.message.delete()
        except:
            pass

        # delete ALL failed verification messages
        failed_ids = context.user_data.get("failed_verify_msg_ids", [])
        for mid in failed_ids:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat_id,
                    message_id=mid
                )
            except:
                pass

        context.user_data.pop("failed_verify_msg_ids", None)

        await query.message.reply_text(
            "✅ **Verified!**\nNow you can use the bot.",
            parse_mode="Markdown"
        )
        return

    await query.answer()

    # ================= ADMIN ONLY =================
    if (data.startswith("broadcast") or data == "stats") and user_id != ADMIN_ID:
        return

    # ================= STATISTICS =================
    if data == "stats":
        async with db_pool.acquire() as conn:

            total = await conn.fetchval(
                "SELECT COUNT(*) FROM user_bot_map WHERE bot_id = $1",
                BOT_ID
            )

            active = await conn.fetchval(
                """
                SELECT COUNT(*) FROM users u
                JOIN user_bot_map m ON u.user_id = m.user_id
                WHERE m.bot_id = $1 AND u.blocked = FALSE
                """,
                BOT_ID
            )


        await query.message.reply_text(
            f"📊 **Statistics**\n\n"
            f"👥 Total Users: {total}\n"
            f"✅ Active Users: {active}",
            parse_mode="Markdown"
        )
        return

    # ================= BROADCAST START =================
    if data == "broadcast":
        context.user_data["awaiting_broadcast"] = True
        await query.message.reply_text(
            "✍️ Send the broadcast message.\n"
            "You will be asked to confirm before sending."
        )
        return

    # ================= BROADCAST CONFIRM =================
    if data == "broadcast_confirm":
        try:
            await query.message.delete()
        except:
            pass

        sent = failed = 0

        async with db_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT u.user_id 
                FROM users u 
                JOIN user_bot_map m ON u.user_id = m.user_id 
                WHERE m.bot_id = $1 AND u.blocked = FALSE
                """,
                BOT_ID
            )

            total_users = len(rows)

            progress_msg = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"<b>📡 Sending Broadcast...</b>\n\n"
                    f"📤 Sent: 0 / {total_users}\n"
                    f"❌ Failed: 0"
                ),
                parse_mode="HTML"
            )

            for index, r in enumerate(rows, start=1):
                uid = r["user_id"]

                try:
                    # Forward if message was forwarded
                    if context.user_data.get("is_forward"):
                        await context.bot.forward_message(
                            chat_id=uid,
                            from_chat_id=context.user_data["broadcast_chat_id"],
                            message_id=context.user_data["broadcast_message_id"]
                        )
                    else:
                        await context.bot.copy_message(
                            chat_id=uid,
                            from_chat_id=context.user_data["broadcast_chat_id"],
                            message_id=context.user_data["broadcast_message_id"]
                        )

                    sent += 1
                    await asyncio.sleep(0.07)

                except Forbidden:
                    failed += 1
                    await conn.execute(
                        "UPDATE users SET blocked = TRUE WHERE user_id = $1",
                        uid
                    )

                except BadRequest:
                    failed += 1
                except Exception as e:
                    print("Broadcast error:", e)
                    failed += 1

                # 🔥 Proper progress update
                if index % 5 == 0 or index == total_users:
                    try:
                        await progress_msg.edit_text(
                            f"<b>📡 Sending Broadcast...</b>\n\n"
                            f"📤 Sent: {sent} / {total_users}\n"
                            f"❌ Failed: {failed}",
                            parse_mode="HTML"
                        )
                    except:
                        pass

        try:
            await progress_msg.delete()
        except:
            pass

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"✅ **Broadcast Completed**\n\n"
                f"📤 Sent: {sent}\n"
                f"❌ Failed: {failed}"
            ),
            parse_mode="Markdown"
        )

        context.user_data.clear()
        return

    # ================= BROADCAST CANCEL =================
    if data == "broadcast_cancel":
        # delete confirm message
        try:
            await query.message.delete()
        except:
            pass

        context.user_data.clear()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Broadcast cancelled."
        )
        return
    
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.user_data.get("awaiting_broadcast"):
        return

    # Store full message object info
    context.user_data["broadcast_message_id"] = update.message.message_id
    context.user_data["broadcast_chat_id"] = update.message.chat_id
    is_forward = update.message.forward_origin is not None
    context.user_data["is_forward"] = is_forward

    buttons = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
        ]
    ]

    await update.message.reply_text(
        "⚠️ <b>Confirm Broadcast</b>\n\nThis message will be sent as it is.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )

    context.user_data["awaiting_broadcast"] = False
    
# ================= REGISTER (PLUG & PLAY) =================

def register_core_panel(app):
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(
        CallbackQueryHandler(
            callback_router,
            pattern="^(check_subscription|stats|broadcast|broadcast_confirm|broadcast_cancel)"
        )
    )

# ================= CONFIG =================

BOT_TOKEN = "8359246645:AAHlKc083uA-mzp0B8pRysQ2F9AO3jSTZiM"

# ================= TEXT MESSAGES =================

GETTING_TEXT = "🔍⚡ <b>Getting information, please wait...</b>"

SUPPORT_TEXT = """
🛠 <b>SUPPORT & HELP</b>
━━━━━━━━━━━━━━━

👨‍💻 <b>Developer:</b> Aditya
📢 <b>Official Channel:</b> @aditya_labs

⚠️ <b>Important Notes:</b>
• <b>This bot only shows publicly available Instagram data</b>
• <b>If the server is busy, please try again later</b>
• <b>Make sure you enter a valid Instagram username</b>

━━━━━━━━━━━━━━━
🔥 <b>Thanks for using our bot!</b>
"""

# ================= UTILS =================
def fetch_instagram_sync(username):
    return get_instagram_info(username)

def clean_username(text: str) -> str:
    text = text.strip()
    if text.startswith("@"):
        text = text[1:]
    return text

def format_message_html(data: dict) -> str:
    return f"""
🔍 <b>INSTAGRAM USER SEARCH RESULTS</b>

👤 <b>Username:</b> {data['username']}
👑 <b>Full Name:</b> {data['full_name']}
📝 <b>Bio:</b> {data['bio'] or 'N/A'}

👥 <b>Followers:</b> {data['followers']}
➡️ <b>Following:</b> {data['following']}
🖼 <b>Posts:</b> {data['posts']}

🔓 <b>Account:</b> {"Public" if not data['private'] else "Private"}
✅ <b>Verified:</b> {"Yes" if data['verified'] else "No"}

🔗 <b>Profile URL:</b>
https://instagram.com/{data['username']}

━━━━━━━━━━━━━━━
🤖 <b>Powered by @aditya_labs</b>
"""

async def any_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_verified(update, context):
        return

async def send_profile_with_hd(update, data):
    caption = format_message_html(data)

    pfp_url = data.get("profile_pic")

    if not pfp_url:
        await update.message.reply_text(
            caption,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    try:
        r = requests.get(pfp_url, timeout=10)
        if r.status_code != 200:
            raise Exception("PFP fetch failed")

        bio = BytesIO(r.content)
        bio.name = "profile.jpg"

        await update.message.reply_photo(
            photo=bio,
            caption=caption,
            parse_mode="HTML"
        )

    except Exception as e:
        print("PFP ERROR:", e)

        # 🔥 FALLBACK: TEXT ONLY
        await update.message.reply_text(
            caption,
            parse_mode="HTML",
            disable_web_page_preview=True
        )


# ================= INSTAGRAM FETCH =================

def get_instagram_info(username: str):
    try:
        # 1️⃣ START ACTOR
        run_url = "https://api.apify.com/v2/acts/apify~instagram-profile-scraper/runs"

        payload = {
            "usernames": [username],
            "includeAboutSection": False
        }

        r = requests.post(
            f"{run_url}?token={APIFY_TOKEN}",
            json=payload,
            timeout=30
        )

        if r.status_code not in (200, 201):
            print("RUN START FAILED:", r.status_code, r.text)
            return None

        run = r.json()["data"]
        run_id = run["id"]
        dataset_id = run["defaultDatasetId"]

        if not dataset_id:
            print("NO DATASET ID")
            return None

        # 2️⃣ WAIT UNTIL RUN FINISHES (MAX ~30s)
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"

        for _ in range(15):  # 15 × 2s = 30s max
            s = requests.get(status_url, timeout=10).json()
            status = s["data"]["status"]

            if status == "SUCCEEDED":
                break

            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                print("RUN FAILED:", status)
                return None

            time.sleep(2)
        else:
            print("RUN TIMEOUT")
            return None

        # 3️⃣ FETCH DATASET
        dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}"
        d = requests.get(dataset_url, timeout=30)

        if d.status_code != 200:
            print("DATASET FETCH FAILED:", d.status_code)
            return None

        data = d.json()
        if not data:
            print("EMPTY DATASET AFTER SUCCESS")
            return None

        user = data[0]

        # 4️⃣ RETURN ONLY WHAT YOU WANT
        return {
            "username": user.get("username"),
            "full_name": user.get("fullName"),
            "bio": user.get("biography"),
            "followers": user.get("followersCount"),
            "following": user.get("followsCount"),
            "posts": user.get("postsCount"),
            "private": user.get("private"),
            "verified": user.get("verified"),
            "profile_pic": user.get("profilePicUrl")
        }

    except Exception as e:
        print("INSTAGRAM FETCH ERROR:", e)
        return None

# ================= COMMANDS =================

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_verify(update, context):
        return

    await update.message.reply_text(
        SUPPORT_TEXT,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 🔒 Verification check
    if not await check_access(update, context):
        return

    # ❌ Username missing
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Usage:</b> /info username",
            parse_mode="HTML"
        )
        return

    # ✅ Clean username (NO .lower())
    username = clean_username(context.args[0]).strip()

    # ⏳ Loading message
    loading_msg = await update.message.reply_text(
        GETTING_TEXT,
        parse_mode="HTML"
    )

    data = None

    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(
            None,
            fetch_instagram_sync,
            username
        )

    except Exception as e:
        print("INFO ERROR:", e)
        data = None

    finally:
        # 🧹 Always remove loader
        try:
            await loading_msg.delete()
        except:
            pass

    # ❌ No data from API
    if not data:
        await update.message.reply_text(
            "⚠️ <b>Instagram did not respond.</b>\n"
            "<i>Please try again after some time.</i>",
            parse_mode="HTML"
        )
        return

    # ✅ Send profile with photo
    await send_profile_with_hd(update, data)

# ================= MAIN =================
def main():
    global db_pool

    loop = asyncio.get_event_loop()
    db_pool = loop.run_until_complete(
        asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5
        )
    )

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    register_core_panel(app)

    app.add_handler(
    MessageHandler(
        ~filters.COMMAND & filters.User(ADMIN_ID),
        broadcast_message
    ))

    # ✅ COMMANDS
    app.add_handler(CommandHandler("start", start), group=1)
    app.add_handler(CommandHandler("info", info), group=1)
    app.add_handler(CommandHandler("support", support), group=1)

    # ✅ ADMIN TEXT (broadcast)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID),
        broadcast_message),
        group=2
    )

    # ✅ NORMAL USER TEXT (verify gate)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND,
        any_text_handler),
        group=3
    )

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
