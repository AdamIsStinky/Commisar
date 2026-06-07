#!/usr/bin/env python3
"""
Rule34 Discord Bot - Railway/GitHub Deploy
Commands:
  !rule34 <tags> [-count:N] [-exclude:tag1,tag2]
  
  Tags: space-separated tags to include
  -count:N : number of images to send (1-15, default 1)
  -exclude:tag1,tag2 : tags to exclude
  -<tag> : alternative way to exclude a single tag
"""

import discord
import aiohttp
import asyncio
import random
import os
import sys
import xml.etree.ElementTree as ET

# ========= CONFIGURATION =========
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
R34_API_KEY = os.environ.get("R34_API_KEY", "")
R34_USER_ID = os.environ.get("R34_USER_ID", "")

if not DISCORD_TOKEN:
    print("[-] ERROR: DISCORD_TOKEN environment variable not set!")
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
    """Fetch posts from the Rule34 API."""
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    valid_urls = []

    limit = min(100, count * 5)

    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "tags": build_tags_string(include_tags, exclude_tags),
        "limit": str(limit),
        "json": "1",
    }

    # Add API key auth if configured
    if R34_API_KEY and R34_USER_ID:
        params["api_key"] = R34_API_KEY
        params["user_id"] = R34_USER_ID

    try:
        async with session.get(
            R34_API, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            if resp.status != 200:
                return None, f"API returned HTTP {resp.status}"

            text = await resp.text()
            text = text.strip()

            # If the response is a JSON string (starts with [ or {)
            if text.startswith("[") or text.startswith("{"):
                import json
                data = json.loads(text)
                
                # Handle {"posts": [...]} wrapper or plain array
                if isinstance(data, dict):
                    posts_list = data.get("posts", [])
                    # Some responses have posts.post (nested)
                    if isinstance(posts_list, dict) and "post" in posts_list:
                        posts_list = posts_list["post"]
                else:
                    posts_list = data

                if not posts_list:
                    return None, "No results found for those tags."

                for post in posts_list:
                    # Handle both direct dict and @attributes wrapping
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
                # Parse XML
                root = ET.fromstring(text)
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
            return None, f"No static images found for tags: {' '.join(include_tags)}. Try different tags."

        random.shuffle(valid_urls)
        return valid_urls[:count], None

    except ET.ParseError as e:
        return None, f"Failed to parse API response: {e}"
    except asyncio.TimeoutError:
        return None, "Request timed out. Try again or use fewer tags."
    except Exception as e:
        return None, f"An error occurred: {str(e)}"


@bot.event
async def on_ready():
    print(f"[+] Logged in as {bot.user} (ID: {bot.user.id})")
    if R34_API_KEY and R34_USER_ID:
        print("[+] Rule34 API key configured")
    else:
        print("[!] No Rule34 API key set - set R34_API_KEY and R34_USER_ID env vars if needed")
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
            await asyncio.sync.sleep(0.3)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
