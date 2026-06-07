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


# ---------- RANKS ----------
ranks = [
    ("citizen", 0),
    ("worker", 20),
    ("party_member", 50),
    ("elite_member", 120),
    ("ministry_official", 250),
    ("leader", 500)
]


# ---------- SHOP ----------
shop_items = {
    "chair": 10,
    "radio": 25,
    "tv": 60,
    "luxury_vase": 120,
    "gold_statue": 250
}


# ---------- BOT ----------
class MyBot(commands.Bot):
    async def setup_hook(self):
        self.loop.create_task(inspection_loop())


bot = MyBot(command_prefix="!", intents=intents)


# ---------- INIT ----------
@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user}")


# ---------- USER ----------
def ensure_user(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,))
    c.execute("INSERT OR IGNORE INTO state (user_id) VALUES (?)", (user_id,))

    conn.commit()
    conn.close()


def get_rank(trust: int):
    current = "citizen"
    for r, req in ranks:
        if trust >= req:
            current = r
    return current


# ---------- INSPECTION (AUTO) ----------
def run_inspection(user_id: str):
    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT money FROM users WHERE id = ?", (user_id,))
    money = c.fetchone()[0]

    c.execute("SELECT SUM(value) FROM inventory WHERE user_id = ?", (user_id,))
    inv = c.fetchone()[0] or 0

    total = money + inv

    c.execute("SELECT money FROM users")
    all_money = [r[0] for r in c.fetchall()]
    target = statistics.median(all_money) if all_money else 50

    confiscated = 0

    if total > target:
        confiscated = total - target

        if money >= confiscated:
            c.execute("UPDATE users SET money = money - ? WHERE id = ?", (confiscated, user_id))
        else:
            c.execute("UPDATE users SET money = 0 WHERE id = ?", (user_id,))

    conn.commit()
    conn.close()

    return target, confiscated


async def inspection_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        await asyncio.sleep(random.randint(60 * 60 * 20, 60 * 60 * 24))  # daily-ish

        conn = database.get_connection()
        c = conn.cursor()

        c.execute("SELECT id FROM users")
        users = c.fetchall()

        for (user_id,) in users:
            c.execute("""
                UPDATE state
                SET is_in_inspection = 1,
                    inspection_end_time = ?
                WHERE user_id = ?
            """, (time.time() + 300, user_id))

            conn.commit()

            target, confiscated = run_inspection(user_id)

            try:
                user = await bot.fetch_user(int(user_id))
                await user.send(
                    f"🏠 DAILY INSPECTION\n"
                    f"📊 Target: {int(target)}\n"
                    f"💰 Confiscated: {confiscated}"
                )
            except:
                pass

        conn.close()


# ---------- COMMANDS ----------

@bot.command()
async def help(ctx):
    await ctx.send(
        "**COMMANDS**\n"
        "!help - show commands\n"
        "!info - game info\n"
        "!work - earn money\n"
        "!shop - view shop\n"
        "!buy <item> - buy item"
    )


@bot.command()
async def info(ctx):
    await ctx.send(
        "🏛️ COMMUNIST SIMULATION GAME\n"
        "Earn money, buy items, survive inspections.\n"
        "Too rich = confiscation.\n"
        "Too poor = struggle."
    )


@bot.command()
async def work(ctx):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT money, trust, job, last_work_timestamp FROM users WHERE id = ?", (user_id,))
    money, trust, job, last_work = c.fetchone()

    now = time.time()

    if now - last_work < 5 * 60 * 60:
        await ctx.send("⏳ Cooldown active")
        return

    reward = random.randint(10, 80)

    c.execute("""
        UPDATE users
        SET money = money + ?,
            last_work_timestamp = ?
        WHERE id = ?
    """, (reward, now, user_id))

    conn.commit()
    conn.close()

    rank = get_rank(trust)

    await ctx.send(f"💼 Worked → +{reward} | Rank: {rank}")


@bot.command()
async def shop(ctx):
    msg = "**SHOP**\n"
    for item, price in shop_items.items():
        msg += f"{item} - {price}\n"
    await ctx.send(msg)


@bot.command()
async def buy(ctx, item):
    user_id = str(ctx.author.id)
    ensure_user(user_id)

    if item not in shop_items:
        await ctx.send("❌ Item not found")
        return

    price = shop_items[item]

    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT money FROM users WHERE id = ?", (user_id,))
    money = c.fetchone()[0]

    if money < price:
        await ctx.send("💸 Not enough money")
        return

    c.execute("UPDATE users SET money = money - ? WHERE id = ?", (price, user_id))
    c.execute("INSERT INTO inventory (user_id, item_name, value) VALUES (?, ?, ?)",
              (user_id, item, price))

    conn.commit()
    conn.close()

    await ctx.send(f"🛒 Bought {item}")


bot.run(TOKEN)
