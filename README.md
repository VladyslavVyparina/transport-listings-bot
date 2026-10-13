# Transport listings bot

A Telegram bot that takes freight listings from drivers and forwarders and relays them into a working chat, with the same rows written to Google Sheets.

## Problem

Listings were posted in several chats in different shapes. The dispatcher wanted one funnel, one working chat, and a sheet that could be filtered later.

## What was built

- `bot.py` is the listing funnel.
- `relay_bot.py` forwards the finished listing into the operations chat.
- `google_sheets.py` appends the row.
- `listings.py` and `locations.py` are the catalogs of cargo and places.
- `scheduler.py` handles timed posts.
- `config.py` holds chat ids and sheet settings. Secrets stay in the environment and in a service-account file that is not published.

## How it works

The user answers the listing questions in Telegram. When the card is complete, the relay posts it to the work chat and the sheet writer adds a row. The service account JSON is required for the sheet and is supplied on the machine that runs the bot, not from this repository.

## Stack

Python, aiogram, Google Sheets.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python bot.py
```

Place your own `service_account.json` beside the bot before the sheet writer will succeed.

## What this public copy leaves out

`service_account.json`.
