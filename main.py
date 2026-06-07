import os
import time
import discord
from discord.ext import commands
import database

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------- USER SETUP ----------

def ensure_user(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    exists = c.fetchone()

    if not exists:
        c.execute("INSERT INTO users (id) VALUES (?)", (user_id,))
        c.execute("INSERT OR IGNORE INTO state (id) VALUES (?)", (user_id,))
        c.execute("INSERT OR IGNORE INTO taxes (id) VALUES (?)", (user_id,))

    conn.commit()
    conn.close()


# ---------- INSPECTION SYSTEM ----------

def is_in_inspection(user_id: str) -> bool:
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT is_in_inspection, inspection_end_time FROM state WHERE id = ?", (user_id,))
    row = c.fetchone()

    conn.close()

    if not row:
        return False

    in_inspection, end_time = row

    return in_inspection == 1 and time.time() < end_time


@bot.check
def global_inspection_check(ctx):
    return not is_in_inspection(str(ctx.author.id))


async def send_inspection_result(user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await user.send("🏠 Inspection completed. (placeholder result)")
    except:
        pass


async def inspection_task():
    await bot.wait_until_ready()

    while not bot.is_closed():
        conn = database.get_connection()
        c = conn.cursor()

        now = time.time()

        c.execute("""
            SELECT id FROM state
            WHERE is_in_inspection = 1 AND inspection_end_time <= ?
        """, (now,))

        users = c.fetchall()

        for (user_id,) in users:
            c.execute("""
                UPDATE state
                SET is_in_inspection = 0
                WHERE id = ?
            """, (user_id,))

            await send_inspection_result(user_id)

        conn.commit()
        conn.close()

        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=10))


# ---------- EVENTS ----------

@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user}")


# ---------- TEST COMMAND ----------

@bot.command()
async def ping(ctx):
    ensure_user(str(ctx.author.id))
    await ctx.send("Pong! 🏓 User registered.")


# ---------- TEST INSPECTION COMMAND ----------

@bot.command()
async def inspect(ctx):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    conn = database.get_connection()
    c = conn.cursor()

    c.execute("""
        UPDATE state
        SET is_in_inspection = 1,
            inspection_end_time = ?
        WHERE id = ?
    """, (time.time() + 300, user_id))  # 5 minutes

    conn.commit()
    conn.close()

    await ctx.send("🔍 Inspection started. Commands locked for 5 minutes.")


# ---------- START BACKGROUND TASK ----------

bot.loop.create_task(inspection_task())


bot.run(TOKEN)
