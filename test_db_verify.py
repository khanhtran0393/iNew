import sqlite3
from app.config import settings

db_path = settings.DATABASE_URL.replace("sqlite:///", "")
print("Database path:", db_path)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]
print(f"Total tables created: {len(tables)}")
for t in sorted(tables):
    cursor.execute(f"SELECT count(*) FROM {t}")
    cnt = cursor.fetchone()[0]
    print(f"  Table {t}: {cnt} rows")
