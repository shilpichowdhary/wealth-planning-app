#!/usr/bin/env python3
"""
Create user accounts for the Wealth Planning app.

Usage:
  python scripts/create_user.py --name "Shilpi" --email "shilpi@firm.com" --role advisor
  python scripts/create_user.py --name "Client A" --email "client@example.com" --role client --case-id <case_id>
"""
import asyncio, argparse, sys, getpass
sys.path.insert(0, ".")
from backend.database import AsyncSessionLocal, create_tables
from backend.models.user import User, UserRole
from backend.services.auth_service import hash_password
from sqlalchemy.exc import IntegrityError

async def main():
    parser = argparse.ArgumentParser(description="Create a user account")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=["advisor", "client"], default="advisor")
    parser.add_argument("--case-id", default=None, help="For client accounts: the case_id to link")
    args = parser.parse_args()

    password = getpass.getpass(f"Password for {args.email}: ")
    await create_tables()
    async with AsyncSessionLocal() as session:
        user = User(
            name=args.name,
            email=args.email,
            hashed_password=hash_password(password),
            role=UserRole(args.role),
            case_id=args.case_id,
        )
        try:
            session.add(user)
            await session.commit()
            print(f"✓ User created: {args.email}")
        except IntegrityError:
            print(f"Error: email {args.email} already exists")
            await session.rollback()

asyncio.run(main())
