"""FastAPI application factory"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from legal_chatbot.api.routes.chat import router as chat_router, store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: start session eviction background task
    task = asyncio.create_task(_evict_loop())
    yield
    # Shutdown: cancel eviction task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _evict_loop():
    """Periodically evict expired sessions"""
    while True:
        await asyncio.sleep(300)  # every 5 minutes
        await store.evict_expired()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title="Vietnamese Legal Chatbot API",
        description="Chat bang tieng Viet tu nhien — he thong tu nhan dien y dinh va goi dung service",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow all for MVP
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)

    return app
