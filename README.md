# M3U/M3U8 Telegram Recording Bot

এই Telegram bot একটি অনুমোদিত HTTP/HTTPS `.m3u` বা `.m3u8` stream নির্দিষ্ট সময় record করে MP4 হিসেবে chat-এ পাঠায়। Recording-এর জন্য container-এর ভিতরে `ffmpeg` ব্যবহার করা হয়।

> এই bot কেবল এমন stream-এর জন্য ব্যবহার করুন যেগুলো record ও redistribute করার অনুমতি আপনার আছে।

## Command

```text
/record <minutes> <m3u8_or_m3u_url>
```

উদাহরণ:

```text
/record 5 https://example.com/live.m3u8
```

## Railway deployment

GitHub repository-টি Railway-তে deploy করার সময় Dockerfile autodetect হলে আলাদা start command প্রয়োজন নেই। Railway service-এর **Variables** অংশে নিচের variable যোগ করুন:

| Variable | Required | Example | Purpose |
|---|---:|---|---|
| `BOT_TOKEN` | হ্যাঁ | BotFather থেকে পাওয়া নতুন token | Telegram authentication |
| `MAX_MINUTES` | না | `120` | এক command-এ সর্বোচ্চ recording সময় |
| `MAX_CONCURRENT_RECORDINGS` | না | `1` | একসঙ্গে কতটি recording চলবে |

`BOT_TOKEN` কখনও `.env` ফাইলে বা public GitHub repository-তে রাখবেন না। Repository-তে থাকা `.env` কেবল placeholder হিসেবে রাখা হয়েছে।

## Local run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN='YOUR_NEW_BOT_TOKEN'
python bot_record_m3u8.py
```

## Implementation details

প্রথমে bot stream-টি codec copy mode-এ দ্রুত MP4 বানানোর চেষ্টা করে। সেটি ব্যর্থ হলে H.264/AAC re-encode fallback চালায়। প্রতিটি কাজ temporary directory-তে সম্পন্ন হয় এবং Telegram-এ পাঠানোর পর local file মুছে ফেলা হয়, তাই recording archive রাখার জন্য Railway volume প্রয়োজন হয় না।

Bot URL-টি `http` বা `https` হতে হবে, recording সময় 1 মিনিট থেকে `MAX_MINUTES`-এর মধ্যে হতে হবে, এবং একাধিক job একসঙ্গে চালানোর সীমা environment variable দিয়ে নিয়ন্ত্রণ করা যায়।

