"""
EDGE Drishti — FastAPI Application Factory
Creates the app, registers all routers, middleware, and WebSocket endpoints.
"""

import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)



import socket

def _get_local_ips():
    ips = {"127.0.0.1", "::1", "localhost"}
    try:
        hostname = socket.gethostname()
        ips.add(socket.gethostbyname(hostname))
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return ips

class MasterAdminMiddleware(BaseHTTPMiddleware):
    PROTECTED_PREFIXES = (
        "/api/master",
        "/api/auth/master",
        "/master-admin",
        "/setup",
    )
    
    ADMIN_HOSTNAME = "edgedrishti-admin.local"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in self.PROTECTED_PREFIXES):
            client_ip = request.client.host if request.client else "unknown"
            host_header = request.headers.get("host", "").split(":")[0].lower()
            is_local_ip   = client_ip in _get_local_ips()
            is_admin_host = host_header == self.ADMIN_HOSTNAME
            if not (is_local_ip or is_admin_host):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Master Admin Console is restricted to the host machine only. "
                            f"Access via https://edgedrishti-admin.local:<port>/master-admin/ "
                            f"directly on the server. (Client IP: {client_ip})"
                        )
                    },
                )
        return await call_next(request)



def create_app() -> FastAPI:
    """Application factory — call once at startup."""
    from backend.core.config import config
    from backend.core.bootstrap import BootstrapManager
    from backend.db.session import DatabaseManager

    
    DatabaseManager.init_db()
    BootstrapManager.bootstrap_database()

    
    app = FastAPI(
        title="EDGE Drishti",
        description="AI-Powered Local CCTV Security Platform",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )

    
    app.add_middleware(MasterAdminMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    
    from backend.auth.unified_auth import router as unified_router
    app.include_router(unified_router)
    from backend.auth.routes_master import router as master_auth_router
    app.include_router(master_auth_router)

    
    from backend.api.camera_routes import router as camera_router
    app.include_router(camera_router)
    from backend.api.admin_routes import router as admin_router
    app.include_router(admin_router)
    from backend.api.user_routes import router as user_router
    app.include_router(user_router)
    from backend.api.master_routes import router as master_router
    app.include_router(master_router)

    
    from backend.api.ws_live import router as ws_router
    app.include_router(ws_router)

    
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "service": "edge-drishti"}

    from fastapi.responses import RedirectResponse

    @app.get("/master-admin")
    async def master_admin_redirect():
        return RedirectResponse(url="/master-admin/login/")

    @app.get("/master-admin/")
    async def master_admin_slash_redirect():
        return RedirectResponse(url="/master-admin/login/")

    @app.get("/api/status/first-boot")
    async def first_boot_status():
        """Frontend checks this to show setup wizard or disable login options."""
        db = DatabaseManager.get_session()
        try:
            is_first = BootstrapManager.is_first_boot(db)
            from backend.db.models import User
            has_users = db.query(User).count() > 0
            return {
                "first_boot": is_first,
                "no_users_exist": not has_users
            }
        finally:
            db.close()

    
    @app.on_event("startup")
    async def on_startup():
        _start_background_services()

    @app.on_event("shutdown")
    async def on_shutdown():
        _stop_background_services()

    # ── Static frontend (Next.js exported build) ───────────────────────────────
    out_dir = Path(config.BASE_DIR) / "out"
    if out_dir.exists():
        app.mount("/", StaticFiles(directory=str(out_dir), html=True), name="frontend")
        logger.info(f"Serving frontend from {out_dir}")
    else:
        logger.warning(f"Frontend /out directory not found. Run 'npm run build' first.")

        @app.get("/")
        async def no_frontend():
            return JSONResponse(
                status_code=503,
                content={"error": "Frontend not built. Run: npm run build"},
            )

    return app


def _start_background_services():
    """Start camera workers, AI pipeline, alert dispatcher, resource monitor."""
    try:
        from backend.cameras.camera_manager import camera_manager
        camera_manager.load_from_db()
        logger.info("Camera workers started [OK]")
    except Exception as e:
        logger.error(f"Failed to start cameras: {e}")

    try:
        from backend.ai.registry import model_registry
        from backend.system.hardware_scan import detect_compute_device
        device = detect_compute_device()
        model_registry.initialize(device=device)
        logger.info(f"AI models initialized on {device} [OK]")
    except Exception as e:
        logger.error(f"Failed to initialize AI models: {e}")

    try:
        from backend.ai.pipeline import pipeline_manager
        from backend.api.ws_live import ws_frame_broadcast
        pipeline_manager.set_ws_broadcast(ws_frame_broadcast)
        pipeline_manager.start_all()
        logger.info("Inference pipelines started [OK]")
    except Exception as e:
        logger.error(f"Failed to start inference pipelines: {e}")

    try:
        from backend.alerts.dispatcher import alert_dispatcher
        alert_dispatcher.start()
        logger.info("Alert dispatcher started [OK]")
    except Exception as e:
        logger.error(f"Failed to start alert dispatcher: {e}")

    try:
        from backend.system.resource_monitor import resource_monitor
        resource_monitor.start()
        logger.info("Resource monitor started [OK]")
    except Exception as e:
        logger.error(f"Failed to start resource monitor: {e}")

    try:
        from backend.network.mdns_service import mdns_service
        from backend.core.config import config
        import threading
        mdns_service.port = config.PUBLIC_PORT
        threading.Thread(target=mdns_service.start, daemon=True).start()
    except Exception as e:
        logger.warning(f"mDNS service failed (app still works on IP): {e}")


def _stop_background_services():
    try:
        from backend.cameras.camera_manager import camera_manager
        camera_manager.shutdown()
    except Exception:
        pass
    try:
        from backend.ai.pipeline import pipeline_manager
        pipeline_manager.shutdown()
    except Exception:
        pass
    try:
        from backend.alerts.dispatcher import alert_dispatcher
        alert_dispatcher.stop()
    except Exception:
        pass
    try:
        from backend.system.resource_monitor import resource_monitor
        resource_monitor.stop()
    except Exception:
        pass
    try:
        from backend.network.mdns_service import mdns_service
        mdns_service.stop()
    except Exception:
        pass
