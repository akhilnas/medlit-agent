"""One-off script: reset failed articles back to pending for a given query.

Usage (local):
    python scripts/reset_failed_articles.py <query_id>

Usage (ECS override):
    command: ["python", "scripts/reset_failed_articles.py", "<query_id>"]
"""

import asyncio
import sys
from pathlib import Path

# Ensure the repo root (/app) is on sys.path when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.core.database import AsyncSessionLocal


async def reset(query_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                UPDATE articles
                SET processing_status = 'pending'
                WHERE clinical_query_id = CAST(:qid AS uuid)
                  AND processing_status = 'failed'
                RETURNING id, pmid
                """
            ),
            {"qid": query_id},
        )
        rows = result.fetchall()
        await db.commit()

    if rows:
        print(f"Reset {len(rows)} articles to 'pending' for query {query_id}:")
        for row in rows:
            print(f"  id={row.id}  pmid={row.pmid}")
    else:
        print(f"No failed articles found for query {query_id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/reset_failed_articles.py <query_id>")
        sys.exit(1)

    asyncio.run(reset(sys.argv[1]))
