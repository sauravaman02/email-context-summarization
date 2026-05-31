#!/bin/bash
set -e

echo "==> Waiting for database to be ready..."
python3 -c "
import asyncio, sys
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

async def wait():
    engine = create_async_engine(settings.database_url)
    for i in range(30):
        try:
            async with engine.connect() as conn:
                await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
            print('Database is ready!')
            await engine.dispose()
            return
        except Exception:
            print(f'  Attempt {i+1}/30 — waiting for database...')
            await asyncio.sleep(2)
    print('ERROR: Database not reachable after 60s')
    sys.exit(1)

asyncio.run(wait())
"

MARKER="/app/.seeded_vol/.seeded"

if [ ! -f "$MARKER" ]; then
    echo "==> Seeding database with sample data..."
    python3 seed.py
    touch "$MARKER"
else
    echo "==> Database already seeded, skipping."
fi

echo "==> Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
