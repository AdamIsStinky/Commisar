import os
import aiohttp
import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------- NSFW GUARD ----------
def nsfw_only(ctx):
    return ctx.channel.is_nsfw()


# ---------- HELP ----------
@bot.command()
async def help(ctx):
    await ctx.send(
        "**IMAGE BOT**\n"
        "!image <query> (NSFW channels only)\n"
        "!cat\n"
        "!dog\n"
        "!meme"
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


# ---------- IMAGE SEARCH (NSFW-GATED) ----------
@bot.command()
async def image(ctx, *, query: str):

    if not ctx.channel.is_nsfw():
        await ctx.send("🔞 This command only works in NSFW-marked channels.")
        return

    # SAFE placeholder image source (replaceable later with compliant API)
    url = f"https://source.unsplash.com/800x600/?{query}"

    embed = discord.Embed(title=f"Image: {query}")
    embed.set_image(url=url)

    await ctx.send(embed=embed)


# ---------- START ----------
bot.run(TOKEN)
