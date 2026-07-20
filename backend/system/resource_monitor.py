"""
System resource monitor — CPU, RAM, disk, GPU, and per-camera FPS.
Runs as a background thread; latest stats available via get_stats().
"""

import threading
import time
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Collects system resource metrics every 2 seconds."""

    def __init__(self):
        self._stats = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="resource-monitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def get_stats(self) -> dict:
        with self._lock:
            return dict(self._stats)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                stats = self._collect()
                with self._lock:
                    self._stats = stats
            except Exception as e:
                logger.debug(f"Resource monitor error: {e}")
            self._stop_event.wait(2.0)

    def _collect(self) -> dict:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        stats = {
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "ram_used_gb": round(mem.used / (1024 ** 3), 2),
            "ram_total_gb": round(mem.total / (1024 ** 3), 2),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024 ** 3), 2),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "gpu": None,
            "cameras": [],
        }

        
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            stats["gpu"] = {
                "name": pynvml.nvmlDeviceGetName(handle),
                "utilization_percent": util.gpu,
                "memory_percent": round(mem_info.used / mem_info.total * 100, 1),
                "memory_used_gb": round(mem_info.used / (1024 ** 3), 2),
                "memory_total_gb": round(mem_info.total / (1024 ** 3), 2),
            }
        except Exception:
            pass

        
        try:
            from backend.cameras.camera_manager import camera_manager
            for cam_id, worker in camera_manager.get_all_workers().items():
                stats["cameras"].append({
                    "camera_id": cam_id,
                    "name": worker.name,
                    "status": worker.status,
                    "fps": worker.fps,
                })
        except Exception:
            pass

        return stats



resource_monitor = ResourceMonitor()
