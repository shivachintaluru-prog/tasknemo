"""FastAPI app factory + static file serving."""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .routes import dashboard, tasks, analytics, sync, config
from .ws import setup_websocket


def create_app() -> FastAPI:
    app = FastAPI(title="TaskNemo", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(dashboard.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(sync.router, prefix="/api")
    app.include_router(config.router, prefix="/api")

    setup_websocket(app)

    # Serve frontend static files if built
    frontend_dist = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "frontend", "dist",
    )
    if os.path.isdir(frontend_dist):
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve the SPA index.html for all non-API routes."""
            file_path = os.path.join(frontend_dist, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(frontend_dist, "index.html"))

    return app
