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

if not DISCORD_TOKEN:
    print("[-] ERROR: DISCORD_TOKEN environment variable not set!")
    sys.exit(1)

if not R34_API_KEY or not R34_USER_ID:
    print("[-] ERROR: R34_API_KEY and R34_USER_ID environment variables must be set!")
    print("[-] Get them from: https://rule34.xxx/index.php?page=account&s=options")
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
    """Parse !rule34 command arguments. Returns (include_tags, exclude_tags, count)"""
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
    """Build the Rule34 API tags string."""
    tags = []
    for tag in include_tags:
        tags.append(tag.replace(" ", "_"))
    for tag in exclude_tags:
        tags.append(f"-{tag.replace(' ', '_')}")
    return " ".join(tags)


async def fetch_posts(session: aiohttp.ClientSession, include_tags: list, exclude_tags: list, count: int):
    """Fetch posts from the Rule34 API with auth."""
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    valid_urls = []
    limit = min(100, count * 5)

    # Build params with auth
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

    full_url = f"{R34_API}?{urlencode(params)}"

    print(f"[DEBUG] Fetching: {R34_API} with tags='{params['tags']}' api_key={'***' if R34_API_KEY else 'NONE'}")

    try:
        async with session.get(
            R34_API, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            text = await resp.text()
            text = text.strip()

            print(f"[DEBUG] API response status: {resp.status}")
            print(f"[DEBUG] API response (first 200 chars): {text[:200]}")

            if resp.status != 200:
                return None, f"API returned HTTP {resp.status}: {text[:100]}"

            # Check for auth error
            if "Missing authentication" in text:
                return None, "Rule34 API rejected authentication. Check your R34_API_KEY and R34_USER_ID."

            # Try JSON first
            if text.startswith("[") or text.startswith("{"):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as e:
                    return None, f"API returned invalid JSON: {e}"

                if isinstance(data, dict):
                    # Handle {"posts": [...]} or {"posts": {"post": [...]}}
                    posts_data = data.get("posts", [])
                    if isinstance(posts_data, dict):
                        posts_list = posts_data.get("post", [])
                    else:
                        posts_list = posts_data
                else:
                    posts_list = data

                if not posts_list:
                    return None, "Rule34 returned no posts for those tags. Check spelling."

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
                except ET.ParseError as e:
                    return None, f"API returned unexpected data: {text[:200]}"

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
        return None, "Request timed out. Try again or use fewer tags."
    except Exception as e:
        return None, f"An error occurred: {str(e)}"


@bot.event
async def on_ready():
    print(f"[+] Logged in as {bot.user}")


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
            "Example: `!rule34 naruto -count:5 -exclude:guro,scat`"
        )
        return

    include_tags, exclude_tags, count = parse_rule34_args(args_text)

    if not include_tags:
        await message.channel.send("Please provide at least one tag to include!")
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
