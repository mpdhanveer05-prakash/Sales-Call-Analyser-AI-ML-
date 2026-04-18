"""
Run once after `alembic upgrade head` to create default users and agents.

Usage:
    cd backend
    python scripts/seed_users.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.user import User, UserRole
from app.models.team import Team
from app.models.agent import Agent
from app.services.auth_service import hash_password


engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def seed(db: AsyncSession) -> None:
    # Team
    result = await db.execute(select(Team).where(Team.name == "Sales Team A"))
    team = result.scalar_one_or_none()
    if not team:
        team = Team(name="Sales Team A", description="Primary outbound sales team")
        db.add(team)
        await db.flush()
        print("Created team: Sales Team A")

    # Admin user (no team)
    result = await db.execute(select(User).where(User.email == settings.seed_admin_email))
    if not result.scalar_one_or_none():
        admin = User(
            email=settings.seed_admin_email,
            hashed_password=hash_password(settings.seed_admin_password),
            full_name="Admin User",
            role=UserRole.ADMIN,
        )
        db.add(admin)
        print(f"Created admin: {settings.seed_admin_email}")

    # Manager user
    result = await db.execute(select(User).where(User.email == settings.seed_manager_email))
    if not result.scalar_one_or_none():
        manager = User(
            email=settings.seed_manager_email,
            hashed_password=hash_password(settings.seed_manager_password),
            full_name="Sales Manager",
            role=UserRole.MANAGER,
            team_id=team.id,
        )
        db.add(manager)
        print(f"Created manager: {settings.seed_manager_email}")

    # Agent user
    result = await db.execute(select(User).where(User.email == settings.seed_agent_email))
    agent_user = result.scalar_one_or_none()
    if not agent_user:
        agent_user = User(
            email=settings.seed_agent_email,
            hashed_password=hash_password(settings.seed_agent_password),
            full_name="Sales Agent",
            role=UserRole.AGENT,
            team_id=team.id,
        )
        db.add(agent_user)
        await db.flush()
        print(f"Created agent user: {settings.seed_agent_email}")

        agent_profile = Agent(
            user_id=agent_user.id,
            team_id=team.id,
            employee_id="EMP001",
        )
        db.add(agent_profile)
        print("Created agent profile: EMP001")

    await db.commit()
    print("\nSeed complete.")


async def main() -> None:
    async with SessionLocal() as db:
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
