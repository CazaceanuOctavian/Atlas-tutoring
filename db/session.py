import json
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

def get_database_connection_string(path_to_secrets: str):
    with open(path_to_secrets, "r") as f:
        secrets = json.load(f)  
    return secrets["db_secret"]['connection_string']

DATABASE_URL=get_database_connection_string('env/env.json')

# Async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # FIXME -> disable in production
    connect_args={
        "ssl": "require"
    }
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

# Dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session