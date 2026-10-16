# Keima Discord Bot

A Discord bot for managing activities, activity membership, and proposed sessions.
Requires Python 3.10 or newer.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a `.env` file containing `DISCORD_TOKEN=your-bot-token`, then run:

```sh
python main.py
```

The bot registers its slash commands at startup. Invite it to a server with the
`bot` and `applications.commands` scopes and permissions to view the session
channel, send messages, read message history, and add reactions.

SQLite files are created in `data/` beside `main.py`. Existing database schemas
and the stored `"0"`/`"1"` flags are retained; no migration is required.

## Commands and permissions

- Everyone can list activities or members, join an activity, and leave one.
- The server owner can create, delete, archive, or unarchive activities; add or
  remove other members; and change core membership.
- The owner or an activity's core members can change its description.
- Only an activity's core members can propose or cancel sessions. Start times
  use UTC and the format `yyyy-MM-dd-HH:mm`.

Deleting an activity also deletes its membership and session history. Archive an
activity to keep its history. Proposed sessions must be cancelled before an
activity can be deleted or archived.

Every 30 seconds, due sessions are checked for a 👍 reaction from each core
member. If all have reacted, the bot mentions the participants, excluding itself.
Completed sessions move to history in a single database transaction. Deleted
proposal messages finish as unconfirmed; temporary Discord errors are logged and
retried without interrupting other sessions.

## Development

```sh
python -m pip install -r requirements-dev.txt
python -m pytest --cov=commands --cov=utils --cov=tasks --cov=main --cov-report=term-missing
ruff check .
ruff format --check .
```

Tests use temporary SQLite databases, the real Discord command registry, and
mocked interactions and reactions. They need no Discord token or network access.
CI runs these checks on Python 3.10 and 3.14 and requires at least 90% coverage.

Command modules keep their explicit slash-command signatures. Shared validation,
permission checks, and instruction responses live in `utils/command_helpers.py`;
SQL and transaction management live in `utils/persistence.py`; UTC parsing lives
in `utils/session_times.py`.
