import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from shems.config import settings
from shems.exceptions import SHEMSException, http_exception_handler, shems_exception_handler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    # PII masking filter on root logger
    from shems.core.security.dpdp import PIIMaskingFilter
    logging.root.addFilter(PIIMaskingFilter())

    # Register event bus notification handlers
    from shems.core.messaging.notification_dispatcher import register_handlers
    register_handlers()
    logger.info("Notification handlers registered")

    # Start Kafka grid feed consumer
    try:
        from shems.ingest.grid_feed_consumer import start_grid_feed_consumer
        await start_grid_feed_consumer()
    except Exception as exc:
        logger.warning("Grid feed consumer startup failed (non-fatal): %s", exc)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    try:
        from shems.ingest.grid_feed_consumer import stop_grid_feed_consumer
        await stop_grid_feed_consumer()
    except Exception:
        pass

    from shems.database import engine
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.3.0",
        description="AI-powered Smart Home Energy Management System",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # DPDP audit log middleware (Phase 3)
    from shems.core.security.dpdp import AuditLogMiddleware
    app.add_middleware(AuditLogMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────────
    app.add_exception_handler(SHEMSException, shems_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # ── Phase 1 routers ──────────────────────────────────────────────────────
    from shems.domains.auth.router import router as auth_router
    from shems.domains.billing.router import router as billing_router
    from shems.domains.household.router import router as household_router
    from shems.domains.tariff.router import router as tariff_router
    from shems.ingest.router import router as ingest_router

    app.include_router(auth_router, prefix="/api/v1/auth")
    app.include_router(household_router, prefix="/api/v1/households")
    app.include_router(billing_router, prefix="/api/v1/billing")
    app.include_router(tariff_router, prefix="/api/v1/tariff")
    app.include_router(ingest_router, prefix="/api/v1/ingest")

    # ── Phase 2 routers ──────────────────────────────────────────────────────
    from shems.domains.grid.router import router as grid_router
    from shems.domains.sustainability.router import router as sustainability_router
    from shems.ml.router import router as ml_router

    app.include_router(grid_router, prefix="/api/v1")
    app.include_router(sustainability_router, prefix="/api/v1")
    app.include_router(ml_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": settings.app_name, "version": "0.3.0"}

    return app


app = create_app()
