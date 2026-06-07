#!/usr/bin/env python3
"""
Rule34 Discord Bot - Railway/GitHub Deploy
Commands:
  !rule34 <tags> [-count:N] [-exclude:tag1,tag2]
  
  Tags: space-separated tags to include
  -count:N : number of images to send (1-15, default 1)
  -exclude:tag1,tag2 : tags to exclude
  -<tag> : alternative way to exclude a single tag

Example:
  !rule34 naruto -count:5 -exclude:guro,scat
  !rule34 sonic -female -count:3
"""

import discord
import aiohttp
import asyncio
import random
import os
import sys

# ========= CONFIGURATION =========
# Read token from environment variable (Railway sets these)
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    print("[-] ERROR: DISCORD_TOKEN environment variable not set!")
    print("[-] Set it in Railway dashboard -> Variables")
    sys.exit(1)

R34_API = "https://api.rule34.xxx/index.php"
MAX_IMAGES = 15
MIN_IMAGES = 1
REQUEST_TIMEOUT = 30
# =================================

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


def parse_rule34_args(text: str):
    """
    Parse the !rule34 command arguments.
    Returns (include_tags, exclude_tags, count)
    """
    parts = text.strip().split()
    include_tags = []
    exclude_tags = []
    count = 1

    for part in parts:
        # Check for -count:N syntax
        if part.startswith("-count:") or part.startswith("-c:"):
            try:
                val = int(part.split(":", 1)[1])
                count = max(MIN_IMAGES, min(MAX_IMAGES, val))
            except (ValueError, IndexError):
                pass
        # Check for -exclude:tag1,tag2 or -e:tag1,tag2 syntax
        elif part.startswith("-exclude:") or part.startswith("-e:"):
            tags_str = part.split(":", 1)[1]
            for tag in tags_str.split(","):
                tag = tag.strip()
                if tag:
                    exclude_tags.append(tag)
        # Single-tag exclusion with -tag
        elif part.startswith("-") and len(part) > 1 and not part.startswith("--"):
            exclude_tags.append(part[1:])
        # Regular include tag
        else:
            include_tags.append(part)

    return include_tags, exclude_tags, count


def build_api_params(include_tags: list, exclude_tags: list, count: int):
    """
    Build the API query parameters.
    Rule34 uses space for AND tags. Excluded tags use '-tag' syntax.
    """
    tags = []
    for tag in include_tags:
        tags.append(tag.replace(" ", "_"))
    for tag in exclude_tags:
        tags.append(f"-{tag.replace(' ', '_')}")

    tags_str = " ".join(tags)
    limit = min(100, count * 3)

    return {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "tags": tags_str,
        "limit": limit,
        "json": 1,
    }


async def fetch_posts(session: aiohttp.ClientSession, params: dict, count: int):
    """
    Fetch posts from the Rule34 API. Returns up to 'count' valid image URLs.
    Filters to only static images (jpg, png, gif, webp).
    """
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    valid_urls = []

    try:
        async with session.get(
            R34_API, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            if resp.status != 200:
                return None, f"API returned HTTP {resp.status}"

            data = await resp.json()

            if not data:
                return None, "No results found for those tags."

            for post in data:
                file_url = post.get("file_url", "")
                if not file_url:
                    continue

                ext = f".{file_url.rsplit('.', 1)[-1].lower()}"
                if ext in image_extensions:
                    valid_urls.append(file_url)

                if len(valid_urls) >= count:
                    break

        if not valid_urls:
            return None, "No static images found for those tags (try different tags)."

        random.shuffle(valid_urls)
        return valid_urls[:count], None

    except asyncio.TimeoutError:
        return None, "Request timed out. Try again or use fewer tags."
    except Exception as e:
        return None, f"An error occurred: {str(e)}"


@bot.event
async def on_ready():
    print(f"[+] Logged in as {bot.user} (ID: {bot.user.id})")
    print("[+] Bot is ready!")


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if not message.content.startswith("!rule34"):
        return

    args_text = message.content[len("!rule34"):].strip()

    if not args_text:
        await message.channel.send(
            "Usage: `!rule34 <tags> [-count:N] [-exclude:tag1,tag2]`\n"
            "Examples:\n"
            "  `!rule34 naruto`\n"
            "  `!rule34 sonic -count:5 -exclude:guro,scat`\n"
            "  `!rule34 star_wars -sith -count:3`"
        )
        return

    include_tags, exclude_tags, count = parse_rule34_args(args_text)

    if not include_tags:
        await message.channel.send("Please provide at least one tag to include!")
        return

    status_msg = await message.channel.send(
        f"Searching for `{' '.join(include_tags)}`"
        f"{f' (excluding: {', '.join(exclude_tags)})' if exclude_tags else ''}"
        f" — fetching {count} image(s)..."
    )

    async with aiohttp.ClientSession() as session:
        params = build_api_params(include_tags, exclude_tags, count)
        urls, error = await fetch_posts(session, params, count)

    if error:
        await status_msg.edit(content=f"Error: {error}")
        return

    if len(urls) == 1:
        await status_msg.edit(content=f"Here's your image for `{' '.join(include_tags)}`:")
        await message.channel.send(urls[0])
    else:
        await status_msg.edit(
            content=f"Found {len(urls)} image(s) for `{' '.join(include_tags)}`:"
        )
        for i, url in enumerate(urls, 1):
            await message.channel.send(f"**{i}.** {url}")
            await asyncio.sleep(0.3)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
