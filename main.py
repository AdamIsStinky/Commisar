import os
import random
import aiohttp
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------- HELP ----------
@bot.command()
async def help(ctx):
    await ctx.send(
        "**IMAGE BOT COMMANDS**\n"
        "!image <query> - random image search\n"
        "!cat - cat image\n"
        "!dog - dog image\n"
        "!meme - random meme"
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
            embed.set_footer(text=f"r/{data['subreddit']}")

            await ctx.send(embed=embed)


# ---------- GENERAL IMAGE SEARCH ----------
@bot.command()
async def image(ctx, *, query: str):
    # Unsplash source (safe image API)
    url = f"https://source.unsplash.com/800x600/?{query}"

    embed = discord.Embed(title=f"Image: {query}")
    embed.set_image(url=url)

    await ctx.send(embed=embed)


# ---------- START ----------
bot.run(TOKEN)
