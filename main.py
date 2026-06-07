import os
import time
import random
import asyncio
import statistics
import discord
from discord.ext import commands
import database

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True


# ---------- JOBS ----------
jobs = {
    "factory_worker": {"min": 10, "max": 30, "trust_req": 0},
    "office_clerk": {"min": 25, "max": 60, "trust_req": 40},
    "state_agent": {"min": 50, "max": 120, "trust_req": 80}
}


# ---------- BOT ----------
class MyBot(commands.Bot):
    async def setup_hook(self):
        self.loop.create_task(inspection_task())


bot = MyBot(command_prefix="!", intents=intents)


# ---------- INIT ----------
@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user}")


# ---------- USER SYSTEM ----------
def ensure_user(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    c.execute("INSERT OR IGNORE INTO state (user_id) VALUES (?)", (user_id,))
    c.execute("INSERT OR IGNORE INTO taxes (user_id) VALUES (?)", (user_id,))

    conn.commit()
    conn.close()


def get_user(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT money, trust, job, last_work_timestamp
        FROM users
        WHERE id = ?
    """, (user_id,))

    row = c.fetchone()
    conn.close()
    return row


# ---------- INSPECTION ----------
def is_in_inspection(user_id: str) -> bool:
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("""
        SELECT is_in_inspection, inspection_end_time
        FROM state
        WHERE user_id = ?
    """, (user_id,))

    row = c.fetchone()
    conn.close()

    if not row:
        return False

    return row[0] == 1 and time.time() < row[1]


@bot.check
def block_during_inspection(ctx):
    return not is_in_inspection(str(ctx.author.id))


async def send_inspection_result(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT money FROM users WHERE id = ?", (user_id,))
    money = c.fetchone()[0]

    c.execute("SELECT SUM(value) FROM inventory WHERE user_id = ?", (user_id,))
    inv = c.fetchone()[0] or 0

    total = money + inv

    c.execute("SELECT money FROM users")
    all_money = [r[0] for r in c.fetchall()]
    target = statistics.median(all_money) if all_money else 100

    confiscated = 0

    if total > target:
        confiscated = total - target

        if money >= confiscated:
            c.execute(
                "UPDATE users SET money = money - ? WHERE id = ?",
                (confiscated, user_id)
            )
        else:
            remaining = confiscated - money
            c.execute("UPDATE users SET money = 0 WHERE id = ?", (user_id,))

    conn.commit()
    conn.close()

    try:
        user = await bot.fetch_user(int(user_id))
        await user.send(
            f"🏠 Inspection complete\n"
            f"📊 Target: {int(target)}\n"
            f"💰 Confiscated: {confiscated}"
        )
    except:
        pass


async def inspection_task():
    await bot.wait_until_ready()

    while not bot.is_closed():
        conn = database.get_connection()
        c = conn.cursor()

        now = time.time()

        c.execute("""
            SELECT user_id
            FROM state
            WHERE is_in_inspection = 1
            AND inspection_end_time <= ?
        """, (now,))

        users = c.fetchall()

        for (user_id,) in users:
            c.execute("""
                UPDATE state
                SET is_in_inspection = 0,
                    inspection_end_time = 0
                WHERE user_id = ?
            """, (user_id,))

            conn.commit()
            await send_inspection_result(user_id)

        conn.close()
        await asyncio.sleep(10)


# ---------- COMMANDS ----------
@bot.command()
async def ping(ctx):
    ensure_user(str(ctx.author.id))
    await ctx.send("Pong 🏓")


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
        WHERE user_id = ?
    """, (time.time() + 300, user_id))

    conn.commit()
    conn.close()

    await ctx.send("🔍 Inspection started (5 min lock)")


@bot.command()
async def work(ctx):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    money, trust, job, last_work = get_user(user_id)
    now = time.time()

    if now - last_work < 5 * 60 * 60:
        await ctx.send("⏳ Cooldown active")
        return

    available = [j for j in jobs if trust >= jobs[j]["trust_req"]]

    if not available:
        await ctx.send("🚫 Unemployable")
        return

    chosen = random.choice(available)
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

    await ctx.send(f"💼 {chosen} → +{payout}")


# ---------- START ----------
bot.run(TOKEN)
