"""Run from api/: PYTHONPATH=app venv/bin/python scripts/cutover_agents.py --maintenance-confirmed"""

import argparse
import asyncio
import os

from database.neo4j.core import get_neo4j_async_driver
from database.pg.core import get_pg_async_engine
from database.redis.redis_ops import RedisManager
from services.agents.cutover import cutover


async def main():
    parser = argparse.ArgumentParser(description="Destructive, offline Agent cutover")
    parser.add_argument("--maintenance-confirmed", action="store_true")
    args = parser.parse_args()
    engine = await get_pg_async_engine()
    neo4j = await get_neo4j_async_driver()
    redis = RedisManager(os.environ["REDIS_HOST"], int(os.getenv("REDIS_PORT", "6379")),
                         os.getenv("REDIS_PASSWORD"))
    try:
        print(await cutover(engine, neo4j, redis, maintenance_confirmed=args.maintenance_confirmed))
    finally:
        await redis.close()
        await neo4j.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
