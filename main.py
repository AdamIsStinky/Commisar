#!/usr/bin/env python3
"""
Rule34 Discord Bot - Railway/GitHub Deploy
Commands:
  !rule34 <tags> [-count:N] [-exclude:tag1,tag2]
"""

import discord
import aiohttp
import asyncio
import random
import os
import sys
import json
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

# ========= CONFIGURATION =========
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
R34_API_KEY = os.environ.get("R34_API_KEY", "")
R34_USER_ID = os.environ.get("R34_USER_ID", "")

# Print ALL environment variables for debugging (excluding sensitive ones)
print("[DEBUG] ALL ENV VARS:")
for key, val in sorted(os.environ.items()):
    if key in ("DISCORD_TOKEN", "R34_API_KEY"):
        print(f"  {key}={val[:10]}... (truncated)" if val else f"  {key}=(EMPTY)")
    else:
        print(f"  {key}={val}")

print(f"[DEBUG] DISCORD_TOKEN set: {bool(DISCORD_TOKEN)}")
print(f"[DEBUG] R34_API_KEY set: {bool(R34_API_KEY)}")
print(f"[DEBUG] R34_USER_ID set: {bool(R34_USER_ID)}")
print(f"[DEBUG] R34_USER_ID value: '{R34_USER_ID}'")
print(f"[DEBUG] R34_API_KEY length: {len(R34_API_KEY)}")

if not DISCORD_TOKEN:
    print("[-] FATAL: DISCORD_TOKEN not set!")
    sys.exit(1)

if not R34_API_KEY or not R34_USER_ID:
    print("[-] WARNING: R34_API_KEY or R34_USER_ID not set!")
    print("[-] The bot will start but API calls will fail!")
    print("[-] Set them in Railway: Variables -> R34_API_KEY and R34_USER_ID")
    # Don't crash — let the bot start so you can see logs
    HAS_AUTH = False
else:
    HAS_AUTH = True
    print(f"[+] R34 API auth configured (user_id: {R34_USER_ID})")

R34_API = "https://api.rule34.xxx/index.php"
MAX_IMAGES = 15
MIN_IMAGES = 1
REQUEST_TIMEOUT = 30
# =================================

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


def parse_rule34_args(text: str):
    parts = text.strip().split()
    include_tags = []
    exclude_tags = []
    count = 1

    for part in parts:
        if part.startswith("-count:") or part.startswith("-c:"):
            try:
                val = int(part.split(":", 1)[1])
                count = max(MIN_IMAGES, min(MAX_IMAGES, val))
            except (ValueError, IndexError):
                pass
        elif part.startswith("-exclude:") or part.startswith("-e:"):
            tags_str = part.split(":", 1)[1]
            for tag in tags_str.split(","):
                tag = tag.strip()
                if tag:
                    exclude_tags.append(tag)
        elif part.startswith("-") and len(part) > 1:
            exclude_tags.append(part[1:])
        else:
            include_tags.append(part)

    return include_tags, exclude_tags, count


def build_tags_string(include_tags: list, exclude_tags: list) -> str:
    tags = []
    for tag in include_tags:
        tags.append(tag.replace(" ", "_"))
    for tag in exclude_tags:
        tags.append(f"-{tag.replace(' ', '_')}")
    return " ".join(tags)


async def fetch_posts(session: aiohttp.ClientSession, include_tags: list, exclude_tags: list, count: int):
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    valid_urls = []
    limit = min(100, count * 5)

    if not HAS_AUTH:
        return None, "Rule34 API credentials not configured. Set R34_API_KEY and R34_USER_ID in Railway variables."

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "tags": build_tags_string(include_tags, exclude_tags),
        "limit": str(limit),
        "json": "1",
        "api_key": R34_API_KEY,
        "user_id": R34_USER_ID,
    }

    print(f"[DEBUG] Request URL: {R34_API}")
    print(f"[DEBUG] Params: page=dapi, s=post, q=index, tags='{params['tags']}', limit={limit}")
    print(f"[DEBUG] Auth: api_key={'***' + R34_API_KEY[-4:] if R34_API_KEY else 'NONE'}, user_id={R34_USER_ID}")

    try:
        async with session.get(
            R34_API, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            text = await resp.text()
            text = text.strip()

            print(f"[DEBUG] Response status: {resp.status}")
            print(f"[DEBUG] Response headers: {dict(resp.headers)}")
            print(f"[DEBUG] Response body (first 300 chars): {text[:300]}")

            if resp.status != 200:
                return None, f"API returned HTTP {resp.status}"

            if "Missing authentication" in text:
                return None, "API rejected auth. Your API key or user_id may be wrong. Generate a new one at https://rule34.xxx/index.php?page=account&s=options"

            # Try JSON
            if text.startswith("[") or text.startswith("{"):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as e:
                    return None, f"Bad JSON response: {e}"

                if isinstance(data, dict):
                    posts_data = data.get("posts", [])
                    if isinstance(posts_data, dict):
                        posts_list = posts_data.get("post", [])
                    else:
                        posts_list = posts_data
                else:
                    posts_list = data

                if not posts_list:
                    return None, "No posts found for those tags."

                for post in posts_list:
                    if isinstance(post, dict) and "@attributes" in post:
                        post = post["@attributes"]
                    file_url = post.get("file_url", "")
                    if not file_url:
                        continue
                    ext = f".{file_url.rsplit('.', 1)[-1].lower()}"
                    if ext in image_extensions:
                        valid_urls.append(file_url)
                    if len(valid_urls) >= count:
                        break
            else:
                # Try XML
                try:
                    root = ET.fromstring(text)
                except ET.ParseError:
                    return None, f"API returned: {text[:200]}"

                for post in root.iter("post"):
                    file_url = post.get("file_url", "")
                    if not file_url:
                        continue
                    ext = f".{file_url.rsplit('.', 1)[-1].lower()}"
                    if ext in image_extensions:
                        valid_urls.append(file_url)
                    if len(valid_urls) >= count:
                        break

        if not valid_urls:
            return None, f"No static images found for tags: {' '.join(include_tags)}."

        random.shuffle(valid_urls)
        return valid_urls[:count], None

    except asyncio.TimeoutError:
        return None, "Request timed out."
    except Exception as e:
        print(f"[DEBUG] Exception: {type(e).__name__}: {e}")
        return None, f"Error: {str(e)}"


@bot.event
async def on_ready():
    print(f"[+] Logged in as {bot.user}")
    print(f"[+] Bot ready! Connected to Discord.")


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
            "Example: `!rule34 naruto -count:5 -exclude:guro`"
        )
        return

    include_tags, exclude_tags, count = parse_rule34_args(args_text)

    if not include_tags:
        await message.channel.send("Please provide at least one tag!")
        return

    status_msg = await message.channel.send(
        f"Searching for `{' '.join(include_tags)}`"
        + (f" (excluding: {', '.join(exclude_tags)})" if exclude_tags else "")
        + f" — fetching {count} image(s)..."
    )

    async with aiohttp.ClientSession() as session:
        urls, error = await fetch_posts(session, include_tags, exclude_tags, count)

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
