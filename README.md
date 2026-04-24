# ArtDatingTgBot

Production-ready skeleton for a Telegram bot with:

- Python 3.11
- aiogram 3
- SQLAlchemy 2
- Alembic
- PostgreSQL

## Project structure

```text
app/
  config.py
  main.py
  db/
    base.py
    models.py
    session.py
  handlers/
    admin.py
    artist.py
    client.py
    start.py
  keyboards/
  services/
  states/
alembic/
requirements.txt
.env.example
README.md
```

## Quick start

1. Create and activate a virtual environment with Python 3.11.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

4. Set your Telegram bot token and PostgreSQL connection string in `.env`.
5. Create the first migration:

   ```bash
   alembic revision --autogenerate -m "init"
   alembic upgrade head
   ```

6. Start the bot:

   ```bash
   python -m app.main
   ```

## Notes

- Long polling is enabled by default.
- `/start` is connected and can be used as a health check for the bot.
- Routers for artist, client, and admin flows are already registered.
- SQLAlchemy is configured in async mode for PostgreSQL via `asyncpg`.

## Migrations

- Alembic uses `Base.metadata` from [app/db/base.py](C:/Users/Мария/PycharmProjects/ArtDatingTgBot/app/db/base.py).
- [alembic/env.py](C:/Users/Мария/PycharmProjects/ArtDatingTgBot/alembic/env.py) is configured for async SQLAlchemy with `postgresql+asyncpg`.
- Model imports are initialized in `env.py`, so `--autogenerate` sees all tables.
- Before running migrations, make sure `.env` contains a valid `DATABASE_URL`.
- Commands:

  ```bash
  alembic revision --autogenerate -m "init"
  alembic upgrade head
  ```

- If you already applied the initial migration, run the next migration for client filters:

  ```bash
  alembic upgrade head
  ```
