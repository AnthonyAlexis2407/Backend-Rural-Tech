import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SQL_FILE = Path(__file__).resolve().parent.parent / 'docs' / 'db' / 'init_schema_and_functions.sql'

def normalize_db_url(url: str) -> str:
    # asyncpg expects postgresql:// not postgresql+asyncpg://
    if url.startswith('postgresql+asyncpg://'):
        return url.replace('postgresql+asyncpg://', 'postgresql://', 1)
    return url

async def run_sql_file(database_url: str, sql_path: Path):
    import asyncpg
    db_url = normalize_db_url(database_url)
    print(f"Connecting to DB: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    conn = await asyncpg.connect(dsn=db_url)
    try:
        sql = sql_path.read_text(encoding='utf-8')
        print(f"Executing SQL file: {sql_path}")
        await conn.execute(sql)
        print("Migration applied successfully.")
    finally:
        await conn.close()

def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise RuntimeError('DATABASE_URL no está configurada en el entorno. Define la variable de entorno o agrega un .env con DATABASE_URL.')
    asyncio.run(run_sql_file(db_url, SQL_FILE))

if __name__ == '__main__':
    main()
