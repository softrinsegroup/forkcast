#!/usr/bin/env python3
import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from storage import close_db, init_db
from models import PromptType


async def cmd_add(args) -> None:
    db = await init_db()
    try:
        prompt_text = Path(args.file).read_text()
        async with db.transaction():
            if args.active:
                await db.execute(
                    "UPDATE prompts SET active=false WHERE type=$1", args.type
                )
            prompt_id = await db.fetchval(
                "INSERT INTO prompts (type, prompt, version, active, model, notes, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
                args.type,
                prompt_text,
                args.version,
                args.active,
                args.model,
                args.notes,
                datetime.now(timezone.utc),
            )
            if prompt_id is None:
                raise RuntimeError("INSERT into prompts returned no id")
        print(
            f"Prompt created: id={prompt_id} type={args.type} version={args.version} active={args.active}"
        )
    finally:
        await close_db(db)


async def cmd_list(args) -> None:
    db = await init_db()
    try:
        rows = await db.fetch(
            "SELECT id, type, version, active, model, notes, created_at FROM prompts ORDER BY type, version"
        )
        if not rows:
            print("No prompts found.")
            return
        print(
            f"{'ID':<4} {'TYPE':<15} {'VER':<5} {'ACTIVE':<8} {'MODEL':<25} {'NOTES':<30} CREATED_AT"
        )
        print("-" * 100)
        for r in rows:
            print(
                f"{r['id']:<4} {r['type']:<15} {r['version']:<5} {str(r['active']):<8} "
                f"{(r['model'] or ''):<25} {(r['notes'] or ''):<30} {r['created_at']}"
            )
    finally:
        await close_db(db)


async def cmd_activate(args) -> None:
    db = await init_db()
    try:
        row = await db.fetchrow("SELECT id, type FROM prompts WHERE id=$1", args.id)
        if row is None:
            print(f"No prompt found with id={args.id}")
            return
        async with db.transaction():
            await db.execute(
                "UPDATE prompts SET active=false WHERE type=$1", row["type"]
            )
            await db.execute("UPDATE prompts SET active=true WHERE id=$1", args.id)
        print(f"Prompt id={args.id} (type={row['type']}) is now active")
    finally:
        await close_db(db)


def main() -> None:
    valid_types = [t.value for t in PromptType]

    parser = argparse.ArgumentParser(description="Manage prompt versions")
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Insert a new prompt version")
    add_p.add_argument("--type", required=True, choices=valid_types)
    add_p.add_argument("--version", required=True, type=int)
    add_p.add_argument(
        "--file", required=True, help="Path to file containing prompt text"
    )
    add_p.add_argument("--model", default=None)
    add_p.add_argument("--notes", default=None)
    add_p.add_argument("--active", action="store_true", default=False)

    sub.add_parser("list", help="List all prompts")

    act_p = sub.add_parser("activate", help="Set a prompt active by id")
    act_p.add_argument("id", type=int)

    args = parser.parse_args()

    if args.command == "add":
        asyncio.run(cmd_add(args))
    elif args.command == "list":
        asyncio.run(cmd_list(args))
    elif args.command == "activate":
        asyncio.run(cmd_activate(args))


if __name__ == "__main__":
    main()
