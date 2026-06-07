import os
import time
import discord
from discord.ext import commands
import database

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------- CONFIG ----------
BAD_WORDS = ["slur1", "slur2", "badword"]  # replace with real filters

SPAM_WINDOW = 5  # seconds
SPAM_LIMIT = 5

user_messages = {}  # user_id -> [timestamps]


# ---------- INIT ----------
@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user}")


# ---------- DB HELPERS ----------
def ensure_user(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))

    conn.commit()
    conn.close()


def add_warn(user_id: str, reason: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("UPDATE users SET warns = warns + 1 WHERE id = ?", (user_id,))
    c.execute(
        "INSERT INTO warn_log (user_id, reason, timestamp) VALUES (?, ?, ?)",
        (user_id, reason, int(time.time()))
    )

    conn.commit()
    conn.close()


def get_warns(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT warns FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()

    conn.close()

    return row[0] if row else 0


# ---------- AUTOMOD CORE ----------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    ensure_user(user_id)

    content = message.content.lower()
    now = time.time()

    # ---------- BAD WORD FILTER ----------
    if any(word in content for word in BAD_WORDS):
        await message.delete()
        add_warn(user_id, "bad_word")

        await message.channel.send(
            f"{message.author.mention} Warning issued (bad language)."
        )

    # ---------- SPAM DETECTION ----------
    if user_id not in user_messages:
        user_messages[user_id] = []

    user_messages[user_id].append(now)

    # keep only recent messages
    user_messages[user_id] = [
        t for t in user_messages[user_id]
        if now - t <= SPAM_WINDOW
    ]

    if len(user_messages[user_id]) > SPAM_LIMIT:
        await message.delete()
        add_warn(user_id, "spam")

        await message.channel.send(
            f"{message.author.mention} Stop spamming."
        )

    await bot.process_commands(message)


# ---------- WARN SYSTEM ----------
@bot.command()
async def warns(ctx, member: discord.Member = None):
    member = member or ctx.author
    count = get_warns(str(member.id))

    await ctx.send(f"⚠️ {member.name} has {count} warnings")


# ---------- CLEAR WARN (ADMIN) ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def clearwarns(ctx, member: discord.Member):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("UPDATE users SET warns = 0 WHERE id = ?", (str(member.id),))

    conn.commit()
    conn.close()

    await ctx.send(f"🧹 Cleared warnings for {member.name}")


# ---------- HELP ----------
@bot.command()
async def help(ctx):
    await ctx.send(
        "**AUTOMOD BOT**\n"
        "!warns [user] - check warnings\n"
        "!clearwarns @user - admin only\n"
        "Auto: anti-spam + bad word filter"
    )


# ---------- START ----------
bot.run(TOKEN)
