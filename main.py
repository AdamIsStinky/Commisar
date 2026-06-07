import os
import aiohttp
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
PIXABAY_KEY = os.getenv("PIXABAY_KEY")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------- HELP ----------
@bot.command()
async def help(ctx):
    await ctx.send(
        "**IMAGE BOT COMMANDS**\n"
        "!image <query> - search images\n"
        "!cat - random cat\n"
        "!dog - random dog\n"
        "!meme - meme image"
    )


# ---------- CAT ----------
@bot.command()
async def cat(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.thecatapi.com/v1/images/search") as r:
            data = await r.json()
            await ctx.send(data[0]["url"])


# ---------- DOG ----------
@bot.command()
async def dog(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://dog.ceo/api/breeds/image/random") as r:
            data = await r.json()
            await ctx.send(data["message"])


# ---------- MEME ----------
@bot.command()
async def meme(ctx):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as r:
            data = await r.json()

            embed = discord.Embed(title=data["title"])
            embed.set_image(url=data["url"])

            await ctx.send(embed=embed)


# ---------- REAL IMAGE SEARCH ----------
@bot.command()
async def image(ctx, *, query: str):

    if not ctx.channel.is_nsfw():
        await ctx.send("🔞 This command only works in NSFW-marked channels.")
        return

    url = (
        "https://pixabay.com/api/"
        f"?key={PIXABAY_KEY}"
        f"&q={query}"
        "&image_type=photo"
        "&per_page=50"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            data = await r.json()

            hits = data.get("hits", [])

            if not hits:
                await ctx.send("❌ No images found.")
                return

            img = hits[0]["largeImageURL"]

            embed = discord.Embed(title=f"Image: {query}")
            embed.set_image(url=img)

            await ctx.send(embed=embed)


# ---------- START ----------
bot.run(TOKEN)
