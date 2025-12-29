import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from sqlalchemy import String, Integer, DateTime, text, select
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aiokafka import AIOKafkaProducer


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "fastapi-sbom-demo"

    postgres_dsn: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_orders: str = "orders"

settings = Settings()



Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    item: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))


engine: AsyncEngine = create_async_engine(
    settings.postgres_dsn,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session



class KafkaClient:
    def __init__(self) -> None:
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            acks="all",
            linger_ms=5,
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish(self, topic: str, key: str, value: bytes) -> None:
        if self._producer is None:
            raise RuntimeError("Kafka producer is not started")
        await self._producer.send_and_wait(topic, key=key.encode("utf-8"), value=value)


kafka = KafkaClient()



class OrderCreate(BaseModel):
    customer_email: str = Field(..., examples=["customer@example.com"])
    item: str = Field(..., examples=["flower-box"])

class OrderOut(BaseModel):
    id: int
    customer_email: str
    item: str
    created_at: datetime



@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await kafka.start()

    yield

    await kafka.stop()
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))
        _ = result.scalar_one()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB not ready: {e}")

    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(payload: OrderCreate, db: AsyncSession = Depends(get_db)):
    order = Order(customer_email=payload.customer_email, item=payload.item)
    db.add(order)
    await db.commit()
    await db.refresh(order)

    event = {
        "event": "order_created",
        "order_id": order.id,
        "customer_email": order.customer_email,
        "item": order.item,
        "created_at": order.created_at.isoformat(),
    }
    await kafka.publish(
        topic=settings.kafka_topic_orders,
        key=str(order.id),
        value=str(event).encode("utf-8"),
    )

    return OrderOut(
        id=order.id,
        customer_email=order.customer_email,
        item=order.item,
        created_at=order.created_at,
    )


@app.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Order).where(Order.id == order_id)
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderOut(
        id=order.id,
        customer_email=order.customer_email,
        item=order.item,
        created_at=order.created_at,
    )

"""
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_email":"a@b.com","item":"flower-box"}'

"""