import os
import discord
from discord.ext import commands
import database

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------- DB HELPERS ----------

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


# ---------- BOT EVENTS ----------

@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user}")


# ---------- TEST COMMAND ----------

@bot.command()
async def ping(ctx):
    ensure_user(str(ctx.author.id))
    await ctx.send("Pong! 🏓 User registered.")


bot.run(TOKEN)
