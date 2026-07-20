
"""
EDGE Drishti — Single Entry Point
Run with:  python run.py

Sequence:
  1. Verify Python 3.11+
  2. Install/verify core Python dependencies
  3. Hardware scan (GPU/CPU detection)
  4. Initialize database and bootstrap first-run data
  5. Generate TLS certificate if missing
  6. Build Next.js frontend if the /out directory is missing
  7. Start all API routers + WebSocket endpoints
  8. Start camera workers for all saved cameras
  9. Start alert dispatcher + resource monitor background tasks
 10. Start Uvicorn (serves API + static frontend)
"""

import sys
import os
import subprocess
import logging
from pathlib import Path

# ── Path setup (MUST be first) ───────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent    
BACKEND_DIR = Path(__file__).parent        

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))


logging.basicConfig(
    level="INFO",
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("edge-drishti")





def check_python_version():
    if sys.version_info < (3, 11):
        logger.error(f"Python 3.11+ required, found {sys.version}")
        sys.exit(1)
    logger.info(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} [OK]")





def install_requirements():
    req_file = BACKEND_DIR / "requirements.txt"
    if not req_file.exists():
        logger.error(f"requirements.txt not found at {req_file}")
        sys.exit(1)

    # Check if core deps and torch are already present
    try:
        import fastapi, sqlalchemy, cryptography, argon2, torch, torchvision, ultralytics
        logger.info("Python dependencies already installed [OK]")
        return
    except ImportError:
        pass

    logger.info("Installing Python dependencies (this may take a few minutes)…")

    
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "setuptools", "wheel", "pip"],
        check=False
    )

    
    import shutil
    has_gpu = False
    if shutil.which("nvidia-smi") is not None:
        try:
            res = subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if res.returncode == 0:
                has_gpu = True
        except Exception:
            pass

    if has_gpu:
        logger.info("NVIDIA GPU detected. Installing GPU-enabled PyTorch & torchvision (CUDA 12.1)...")
        torch_index = "https://download.pytorch.org/whl/cu121"
    else:
        logger.info("No NVIDIA GPU detected. Installing CPU-only PyTorch & torchvision...")
        torch_index = "https://download.pytorch.org/whl/cpu"

    # Pre-install torch and torchvision from the correct index
    result_torch = subprocess.run(
        [sys.executable, "-m", "pip", "install", "torch", "torchvision", "--index-url", torch_index],
        cwd=str(BACKEND_DIR)
    )
    if result_torch.returncode != 0:
        logger.warning(f"Failed to install PyTorch from {torch_index}. Will try standard PyPI fallback.")

    
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        cwd=str(BACKEND_DIR)
    )
    if result.returncode != 0:
        logger.error(
            "Dependency installation failed. "
            "Try running manually:\n"
            f"  pip install setuptools wheel --upgrade\n"
            f"  pip install -r {req_file}"
        )
        sys.exit(1)
    logger.info("Dependencies installed [OK]")



# 3. Build Next.js frontend (if not already built)

def build_frontend():
    frontend_out = ROOT_DIR / "out"
    package_json = ROOT_DIR / "package.json"

    if frontend_out.exists() and (frontend_out / "index.html").exists():
        logger.info("Frontend already built [OK]")
        return

    if not package_json.exists():
        logger.warning("package.json not found — skipping frontend build")
        return

    logger.info("Building Next.js frontend…")

    # ── npm helper: works on Windows PowerShell (execution policy safe) ───
    def npm(*args):
        """Run npm command cross-platform without PS execution policy issues."""
        if sys.platform == "win32":
            
            return subprocess.run(
                ["cmd", "/c", "npm"] + list(args),
                cwd=str(ROOT_DIR)
            )
        else:
            return subprocess.run(["npm"] + list(args), cwd=str(ROOT_DIR))

    # Install node_modules if missing
    if not (ROOT_DIR / "node_modules").exists():
        logger.info("Installing npm packages…")
        result = npm("install")
        if result.returncode != 0:
            logger.warning(
                "npm install failed. You may need to:\n"
                "  1. Install Node.js from https://nodejs.org\n"
                "  2. Run manually:  npm install  then  npm run build\n"
                "     (in the project root)\n"
                "The backend will still start; the frontend will show an error page."
            )
            return

    # Build (with output: 'export' in next.config.mjs, `npm run build`
    
    logger.info("Running npm run build…")
    result = npm("run", "build")
    if result.returncode != 0:
        logger.warning(
            "npm build failed. Run manually:  npm run build  in the project root."
        )
        return

    if (frontend_out / "index.html").exists():
        logger.info("Frontend built successfully [OK]")
    else:
        logger.warning("Build finished but /out/index.html not found — check Next.js config")





def main():
    logger.info("=" * 70)
    logger.info("  EDGE Drishti — AI-Powered CCTV Security Platform")
    logger.info("=" * 70)

    check_python_version()
    install_requirements()
    build_frontend()

    
    try:
        from backend.core.config import config
        from backend.app import create_app
    except ImportError as e:
        logger.error(f"Failed to import backend modules: {e}")
        logger.error(
            "Ensure dependencies are installed:\n"
            f"  pip install -r {BACKEND_DIR / 'requirements.txt'}"
        )
        sys.exit(1)

    app = create_app()

    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("10.255.255.255", 1))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "127.0.0.1"

    port = config.PUBLIC_PORT
    tls = config.TLS_CERT_PATH.exists()
    scheme = "https" if tls else "http"

    logger.info("")
    logger.info("  ┌─────────────────────────────────────────────────────────────┐")
    logger.info(f"  │  User Portal:        {scheme}://edgedrishti.local:{port}/")
    logger.info(f"  │  Admin Portal:       {scheme}://edgedrishti.local:{port}/")
    logger.info(f"  │  Master Admin:       {scheme}://edgedrishti-admin.local:{port}/master-admin/")
    logger.info(f"  │    (loopback mDNS — only accessible on this machine)")
    logger.info(f"  │    Fallback:         {scheme}://localhost:{port}/master-admin/")
    logger.info(f"  │                      {scheme}://127.0.0.1:{port}/master-admin/")
    logger.info(f"  │  API Docs:           {scheme}://edgedrishti.local:{port}/docs")
    logger.info(f"  │  Fallback (LAN IP):  {scheme}://{lan_ip}:{port}")
    logger.info("  └─────────────────────────────────────────────────────────────┘")
    logger.info("")

    
    try:
        import uvicorn
        uvicorn_kwargs = dict(
            app=app,
            host=config.PUBLIC_HOST,
            port=port,
            log_level=config.LOG_LEVEL.lower(),
            access_log=False,     
        )
        if tls:
            uvicorn_kwargs["ssl_certfile"] = str(config.TLS_CERT_PATH)
            uvicorn_kwargs["ssl_keyfile"] = str(config.TLS_KEY_PATH)
        else:
            logger.warning("TLS certificate not found — running over HTTP (not recommended for production)")

        uvicorn.run(**uvicorn_kwargs)

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
