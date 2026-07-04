"""Issue an API key from the CLI (beta signup path until the dashboard ships).

Usage:
    python pipeline/issue_key.py dev@example.com
    python pipeline/issue_key.py dev@example.com --name "prod key" --quota 5000

Prerequisites:
    - PostgreSQL running (docker-compose up -d postgres)
    - Migrations applied (alembic upgrade head)
"""

import argparse
import asyncio
import sys

sys.path.insert(0, ".")  # allow `python pipeline/issue_key.py` from repo root

from sqlalchemy import select

from backend.auth.keys import generate_api_key
from backend.auth.models import ApiKey, User
from backend.db import AsyncSessionLocal


async def issue_key(email: str, name: str, quota: int, rate: int) -> str:
    """Create (or reuse) the user for `email` and mint a new API key. Returns the full key."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(email=email)
            session.add(user)
            await session.flush()
            print(f"[issue_key] Created user {email}")

        full_key, key_hash, prefix = generate_api_key()
        session.add(
            ApiKey(
                user_id=user.id,
                key_hash=key_hash,
                key_prefix=prefix,
                name=name,
                monthly_quota=quota,
                rate_limit_per_minute=rate,
            )
        )
        await session.commit()
        return full_key


def main() -> None:
    """Parse args and print the new key exactly once."""
    parser = argparse.ArgumentParser(description="Issue a Cryo API key")
    parser.add_argument("email", help="Account email address")
    parser.add_argument("--name", default="default", help="Key label")
    parser.add_argument("--quota", type=int, default=1000, help="Monthly request quota")
    parser.add_argument("--rate", type=int, default=60, help="Requests per minute")
    args = parser.parse_args()

    key = asyncio.run(issue_key(args.email, args.name, args.quota, args.rate))
    print("\n  API key (shown once — store it now):\n")
    print(f"    {key}\n")


if __name__ == "__main__":
    main()
