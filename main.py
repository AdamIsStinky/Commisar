import os
import sys

# ====== DEBUG: Dump ALL env vars at startup ======
print("=" * 60)
print("STARTUP DEBUG - Environment Variables:")
print(f"CWD: {os.getcwd()}")
print(f"Files in CWD: {os.listdir('.')}")
print()

# Print every env var
for key, value in sorted(os.environ.items()):
    print(f"  ENV: {key}={value[:50] if value else '(empty)'}")

print()
print(f"DIRECT CHECK - os.environ.get('R34_API_KEY') = {repr(os.environ.get('R34_API_KEY'))}")
print(f"DIRECT CHECK - os.environ.get('R34_USER_ID') = {repr(os.environ.get('R34_USER_ID'))}")
print(f"DIRECT CHECK - os.environ.get('DISCORD_TOKEN') = {'SET' if os.environ.get('DISCORD_TOKEN') else 'NOT SET'}")
print("=" * 60)
# ================================================

# Now set the values
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
R34_API_KEY = os.environ.get("R34_API_KEY", "")
R34_USER_ID = os.environ.get("R34_USER_ID", "")

# If env vars are empty, try reading from a .env file (fallback)
if not R34_API_KEY or not R34_USER_ID:
    env_file = os.path.join(os.getcwd(), ".env")
    print(f"[INFO] Checking for .env file at: {env_file}")
    if os.path.exists(env_file):
        print("[INFO] .env file found! Reading it...")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key == "R34_API_KEY" and not R34_API_KEY:
                        R34_API_KEY = val
                        print(f"[INFO] Loaded R34_API_KEY from .env")
                    elif key == "R34_USER_ID" and not R34_USER_ID:
                        R34_USER_ID = val
                        print(f"[INFO] Loaded R34_USER_ID from .env")
                    elif key == "DISCORD_TOKEN" and not DISCORD_TOKEN:
                        DISCORD_TOKEN = val
                        print(f"[INFO] Loaded DISCORD_TOKEN from .env")

print(f"[INFO] FINAL VALUES:")
print(f"  DISCORD_TOKEN: {'SET' if DISCORD_TOKEN else 'MISSING'}")
print(f"  R34_API_KEY: {'SET (' + R34_API_KEY[:5] + '...)' if R34_API_KEY else 'MISSING'}")
print(f"  R34_USER_ID: {R34_USER_ID if R34_USER_ID else 'MISSING'}")

if not DISCORD_TOKEN:
    print("FATAL: No Discord token found!")
    sys.exit(1)

if not R34_API_KEY or not R34_USER_ID:
    print("FATAL: R34_API_KEY or R34_USER_ID is empty!")
    print("Set them either as Railway env vars or in a .env file in your repo root.")
    print("Format: R34_API_KEY=yourkey R34_USER_ID=yourid")
    sys.exit(1)

# ====== REST OF BOT CODE ======
import discord
import aiohttp
import asyncio
import random
import json
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

R34_API = "https://api.rule34.xxx/index.php"
MAX_IMAGES = 15
MIN_IMAGES = 1
REQUEST_TIMEOUT = 30

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

    print(f"[DEBUG] API request: tags='{params['tags']}' user_id={R34_USER_ID} key_len={len(R34_API_KEY)}")

    try:
        async with session.get(
            R34_API, params=params, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            text = await resp.text()
            text = text.strip()

            print(f"[DEBUG] API response status: {resp.status}")
            print(f"[DEBUG] API response: {text[:200]}")

            if resp.status != 200:
                return None, f"API returned HTTP {resp.status}"
            if "Missing authentication" in text:
                return None, f"Auth rejected! Check your R34_API_KEY and R34_USER_ID"

            if text.startswith("[") or text.startswith("{"):
                data = json.loads(text)
                if isinstance(data, dict):
                    posts_data = data.get("posts", [])
                    if isinstance(posts_data, dict):
                        posts_list = posts_data.get("post", [])
                    else:
                        posts_list = posts_data
                else:
                    posts_list = data
                if not posts_list:
                    return None, "No posts found."
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
            return None, f"No images found for: {' '.join(include_tags)}."
        random.shuffle(valid_urls)
        return valid_urls[:count], None
    except asyncio.TimeoutError:
        return None, "Request timed out."
    except Exception as e:
        print(f"[DEBUG] Exception: {e}")
        return None, f"Error: {str(e)}"


@bot.event
async def on_ready():
    print(f"[+] Bot logged in as {bot.user}")
    print(f"[+] Bot is ready!")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if not message.content.startswith("!rule34"):
        return

    args_text = message.content[len("!rule34"):].strip()
    if not args_text:
        await message.channel.send("Usage: `!rule34 <tags> [-count:N] [-exclude:tag1,tag2]`")
        return

    include_tags, exclude_tags, count = parse_rule34_args(args_text)
    if not include_tags:
        await message.channel.send("Please provide at least one tag!")
        return

    status_msg = await message.channel.send(
        f"Searching for `{' '.join(include_tags)}`"
        + (f" (excluding: {', '.join(exclude_tags)})" if exclude_tags else "")
        + f" — {count} image(s)..."
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
        await status_msg.edit(content=f"Found {len(urls)} image(s):")
        for i, url in enumerate(urls, 1):
            await message.channel.send(f"**{i}.** {url}")
            await asyncio.sleep(0.3)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
