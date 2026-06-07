import os
import time
import random
import discord
from discord.ext import commands
import database

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------- JOBS ----------

jobs = {
    "factory_worker": {"min": 10, "max": 30, "trust_req": 0},
    "office_clerk": {"min": 25, "max": 60, "trust_req": 40},
    "state_agent": {"min": 50, "max": 120, "trust_req": 80}
}


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


def get_user(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT money, trust, job, last_work_timestamp FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()

    conn.close()
    return row


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


# ---------- COMMANDS ----------

@bot.command()
async def ping(ctx):
    ensure_user(str(ctx.author.id))
    await ctx.send("Pong! 🏓 User registered.")


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
    """, (time.time() + 300, user_id))

    conn.commit()
    conn.close()

    await ctx.send("🔍 Inspection started. Commands locked for 5 minutes.")


@bot.command()
async def work(ctx):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    money, trust, job, last_work = get_user(user_id)

    now = time.time()

    # 5 hour cooldown
    if now - last_work < 5 * 60 * 60:
        remaining = int((5 * 60 * 60) - (now - last_work))
        await ctx.send(f"⏳ You are tired. Try again in {remaining // 60} minutes.")
        return

    available_jobs = [
        j for j, data in jobs.items()
        if trust >= data["trust_req"]
    ]

    if not available_jobs:
        await ctx.send("🚫 You are unemployable.")
        return

    chosen = random.choice(available_jobs)
    payout = random.randint(jobs[chosen]["min"], jobs[chosen]["max"])

    conn = database.get_connection()
    c = conn.cursor()

    c.execute("""
        UPDATE users
        SET money = money + ?,
            job = ?,
            last_work_timestamp = ?
        WHERE id = ?
    """, (payout, chosen, now, user_id))

    conn.commit()
    conn.close()

    await ctx.send(f"💼 You worked as **{chosen}** and earned **{payout} credits**.")


# ---------- START BACKGROUND TASK ----------

bot.loop.create_task(inspection_task())


bot.run(TOKEN)
