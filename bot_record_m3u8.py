#!/usr/bin/env python3
import asyncio
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAX_MINUTES = int(os.getenv("MAX_MINUTES", "120"))
MAX_CONCURRENT_RECORDINGS = int(os.getenv("MAX_CONCURRENT_RECORDINGS", "1"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

recording_slots = asyncio.Semaphore(MAX_CONCURRENT_RECORDINGS)


def valid_stream_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and len(value) <= 2048


async def run_ffmpeg(url: str, seconds: int, output: Path, reencode: bool = False) -> tuple[int, str]:
    args = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
        "-allowed_extensions", "ALL",
        "-i", url, "-t", str(seconds),
    ]
    if reencode:
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-c", "copy"]
    args += ["-movflags", "+faststart", str(output)]

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    return process.returncode, stderr.decode(errors="replace")[-4000:]


async def record_stream(url: str, seconds: int, output: Path) -> None:
    code, log = await run_ffmpeg(url, seconds, output, reencode=False)
    if code == 0 and output.exists() and output.stat().st_size > 0:
        return

    output.unlink(missing_ok=True)
    code, fallback_log = await run_ffmpeg(url, seconds, output, reencode=True)
    if code != 0 or not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg failed: {(fallback_log or log).strip()[-1500:]}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ব্যবহার:\n/record <minutes> <m3u8_or_m3u_url>\n\n"
        f"সর্বোচ্চ সময়: {MAX_MINUTES} মিনিট"
    )


async def record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    if len(context.args) != 2:
        await update.message.reply_text("ব্যবহার: /record <minutes> <m3u8_or_m3u_url>")
        return

    try:
        minutes = int(context.args[0])
    except ValueError:
        await update.message.reply_text("প্রথম argument-টি পূর্ণসংখ্যা মিনিট হতে হবে।")
        return

    url = context.args[1].strip()
    if minutes < 1 or minutes > MAX_MINUTES:
        await update.message.reply_text(f"সময় 1 থেকে {MAX_MINUTES} মিনিটের মধ্যে দিন।")
        return
    if not valid_stream_url(url):
        await update.message.reply_text("শুধু বৈধ http/https m3u বা m3u8 URL দিন।")
        return

    await update.message.reply_text(f"{minutes} মিনিটের stream recording শুরু হয়েছে।")
    temp_dir = Path(tempfile.mkdtemp(prefix="tgrec_"))
    output = temp_dir / f"recording_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.mp4"

    try:
        async with recording_slots:
            await record_stream(url, minutes * 60, output)
        with output.open("rb") as video_file:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_file,
                supports_streaming=True,
                caption=f"Recording: {minutes} মিনিট",
            )
    except Exception as exc:
        await update.message.reply_text(
            "Recording ব্যর্থ হয়েছে। URL live/accessible কি না এবং stream format ঠিক আছে কি না দেখুন।"
        )
        print(f"recording error: {exc}")
    finally:
        for item in temp_dir.glob("*"):
            item.unlink(missing_ok=True)
        temp_dir.rmdir()


def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(False).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("record", record))
    print("Bot is running")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
