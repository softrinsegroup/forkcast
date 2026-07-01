from uuid import UUID
import asyncpg

from models import User


class UserStore:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def create(self, user: User) -> UUID:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                user_id = await conn.fetchval(
                    "INSERT INTO users (name, email, google_sub) "
                    "VALUES ($1, $2, $3) RETURNING id",
                    user.name,
                    user.email,
                    user.google_sub,
                )
                if user_id is None:
                    raise RuntimeError("INSERT into users returned no rowid")

                print(
                    f"User created: id={user_id} email={user.email} google_sub={user.google_sub}"
                )

                return user_id

    async def get(self, id: UUID) -> User | None:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", id)
            if row is None:
                return None
            return self._parse_user(dict(row))

    async def update(self, user: User) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE users SET name=$1, email=$2, google_sub=$3 WHERE id=$4",
                    user.name,
                    user.email,
                    user.google_sub,
                    user.id,
                )

    async def delete(self, id: UUID) -> None:
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM users WHERE id = $1", id)

    def _parse_user(self, row: dict) -> User:
        return User(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            google_sub=row["google_sub"],
            created_at=row["created_at"],
        )
