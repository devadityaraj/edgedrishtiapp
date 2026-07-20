# EDGE Drishti - AI-Powered CCTV Security Platform

**100% Local Processing • No Cloud Dependencies • Full Data Ownership**

EDGE Drishti is an enterprise-grade AI-powered CCTV security system that runs entirely on-premise. All video processing, AI inference, and sensitive data remain strictly on your local hardware.

---

## Core Architecture

EDGE Drishti is structured into distinct backend modules and a unified Next.js frontend:

### 1. Backend Modules (Python)
- **`run.py` & `app.py`**: The entrypoint and ASGI FastAPI server, initializing and managing startup loops.
- **`core/`**: Configuration parsing (`config.py`) and first-run bootstrapping (`bootstrap.py`).
- **`security/`**: Lockout state machines, AES-256-GCM, Argon2id, and browser fingerprinting.
- **`db/`**: Database models (`models.py`) mapping 16 tables, session management (`session.py`).
- **`cameras/`**: Live stream ingestions (USB, Webcams, RTSP, UDP, HTTP, Local Video files).
- **`ai/`**: Unified model registry (`registry.py`), shared YOLO manager (`shared_yolo.py`), and inference loops (`pipeline.py`).
- **`alerts/`**: Queue dispatchers (`dispatcher.py`) and channels like Telegram (`telegram_channel.py`).
- **`system/`**: GPU/CPU/Memory diagnostics (`resource_monitor.py` and `hardware_scan.py`).
- **`audit/`**: Append-only tamper-evident audit logging (`audit_logger.py`).

### 2. Frontend Modules (Next.js + Tailwind + TypeScript)
- **`app/`**: Pages including setup, login, User, Admin, and Master Admin dashboards.
- **`components/`**: Live video players, ROI editors, System Stats charts, and Guards.
- **`lib/`**: Custom REST and WebSocket clients (`api-client.ts`, `ws-client.ts`).
- **`store/`**: UI, Camera, and Auth states powered by Zustand.

---

## System Flow & Pipelines

### Video Ingestion Flow
1. Camera worker thread reads frames from the configured source (USB Webcam, RTSP stream, or Local MP4 file).
2. Frames are decoded via OpenCV into NumPy arrays.
3. The raw frame is pushed to a shared thread-safe queue.

### AI Inference & Consolidated YOLO Pass
1. The inference thread pulls the newest frame from the queue.
2. If **Person, Object, Vehicle, or Animal** models are enabled, they are consolidated into a **single unified YOLOv8 tracking pass** (saving CPU/GPU memory).
3. The shared YOLO manager runs `model.track()` with the combined subset of active class IDs.
4. Output detections are mapped back to their respective parent models.
5. If **Fire/Smoke** or other custom classifiers are enabled, they run their respective heuristic or custom inference steps sequentially on the same frame.
6. Allowed class filters and Camera Region-of-Interest (ROI) bounds are validated.
7. Valid detections draw labels and bounding boxes to the frame overlay.
8. The final annotated frame is broadcasted to connected browser WebSockets and queued for recording if a trigger occurs.

---

## Cryptography & Encryption

EDGE Drishti follows strict cryptographic design principles for secure operations:

### 1. Transport Security (HTTPS)
- First-boot initialization generates a unique, self-signed TLS certificate locally.
- All communications are routed via Uvicorn over HTTPS.

### 2. Authentication & Security
- **Passwords & PINs**: Hashed using Argon2id (using random 16-byte salts, 64MB memory, and 2 iterations).
- **Client-Side Obfuscation**: Passwords are pre-hashed with SHA-256 before transmission to protect against transit snooping.
- **Key Exchange**: Local clients and APIs negotiate session security using X25519 ECDH.

### 3. Encryption at Rest
- Sensitive data fields (such as RTSP credentials, recovery keys, configuration variables) are encrypted in the database using AES-256-GCM.
- Video clips and snapshots are saved in an encrypted storage directory.

---

## Authentication Security

### 1. Localhost Isolation
- **Master Admin Dashboard** (`/master-admin`) is blocked at the ASGI middleware level for all non-loopback requests. It can only be loaded from `127.0.0.1` or `localhost`.

### 2. Progressive Lockout State Machine
- Failed attempts are tracked in the `login_attempts` table.
- **Attempt 1-2**: Returns a generic invalid credentials message.
- **Attempt 3-4**: Triggers a progressive 30-second lockout.
- **Attempt 5**: Disables the account. It can only be unlocked manually by an Admin or Master Admin.

### 3. Trusted Devices
- Users can "Remember Device" on login. This creates a secure, cryptographically signed token bound to a 16-point browser fingerprint.
- Valid tokens bypass login checks for exactly 24 hours from the same device browser.

---

## Database Schema

EDGE Drishti uses an SQLite database (`app.db`) managed through SQLAlchemy ORM:

1. **`users`**: User profiles, roles (User, Admin, Master Admin), and active state flags.
2. **`sessions`**: Secure access tokens mapped to expired datetimes.
3. **`trusted_devices`**: Browser fingerprint hashes with 24-hour expiration tokens.
4. **`login_attempts`**: Append-only log of logins containing fingerprints and lockout flags.
5. **`cameras`**: Camera name, hardware source paths, resolution, status, and custom properties.
6. **`ai_models`**: Global toggles, confidence thresholds, and class limits for running engines.
7. **`camera_model_links`**: Camera-to-AI configurations (ROI zones, custom schedules, and FPS caps).
8. **`detection_events`**: Tracked objects, bounding box JSON, clip references, and timestamp.
9. **`faces`**: Enrolled biometric facial identities and reference hashes.
10. **`alert_contacts`**: Registered Telegram chat IDs and e-mail targets.
11. **`alert_log`**: Deliveries, status reports, and failure exceptions.
12. **`notifications`**: User panel alert feeds.
13. **`system_config`**: Encrypted global system settings.
14. **`audit_log`**: Administrative logs cryptographically chained to prevent alteration.

---

## Quick Start & Usage

### Prerequisites
- Node.js 18+
- Python 3.11+ (with virtualenv)

### Installation & Execution
1. Activate virtual environment and install packages:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   npm install
   ```
2. Build and compile frontend assets:
   ```bash
   npm run build
   ```
3. Run the application:
   ```bash
   ./start.sh
   ```
4. Access endpoints:
   - User & Admin Portal: `https://localhost:8443`
   - Master Admin Console (Localhost only): `https://localhost:8443/master-admin/`
