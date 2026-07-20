"""
Hardware detection utility.
Detects available compute devices (NVIDIA CUDA, AMD ROCm, Intel OpenVINO, CPU).
"""

import logging

logger = logging.getLogger(__name__)


def detect_compute_device() -> str:
    """
    Probe available AI inference devices and return the best one.
    Priority: CUDA > ROCm > OpenVINO > CPU
    """
    
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory // (1024 ** 3)
            logger.info(f"Using NVIDIA CUDA GPU: {gpu_name} ({vram} GB VRAM)")
            return "cuda"
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"CUDA probe failed: {e}")

    
    try:
        import torch
        if hasattr(torch, "hip") and torch.cuda.is_available():  
            logger.info("Using AMD ROCm GPU")
            return "cuda"  
    except Exception:
        pass

    
    try:
        from openvino.runtime import Core
        core = Core()
        devices = core.available_devices
        if "GPU" in devices:
            logger.info("Using Intel OpenVINO GPU")
            return "openvino"
        elif devices:
            logger.info(f"Using Intel OpenVINO: {devices}")
            return "openvino"
    except ImportError:
        pass
    except Exception:
        pass

    logger.info("Using CPU for inference (no GPU detected)")
    return "cpu"


def get_hardware_report() -> dict:
    """Return a comprehensive hardware capability report."""
    import psutil
    import platform

    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    report = {
        "platform": platform.system(),
        "cpu": {
            "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(logical=True),
            "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
            "active_load_percent": cpu_percent,
        },
        "ram_gb": round(mem.total / (1024 ** 3), 1),
        "ram_usage": {
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "used_gb": round(mem.used / (1024 ** 3), 2),
            "free_gb": round(mem.available / (1024 ** 3), 2),
            "percent": mem.percent,
        },
        "disk_usage": {
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "used_gb": round(disk.used / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
            "percent": disk.percent,
        },
        "gpu": None,
        "inference_device": detect_compute_device(),
        "torch_available": False,
        "ultralytics_available": False,
        "face_recognition_available": False,
        "insightface_available": False,
    }

    try:
        import torch
        report["torch_available"] = True
        if torch.cuda.is_available():
            report["gpu"] = {
                "name": torch.cuda.get_device_name(0),
                "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 1),
                "backend": "CUDA",
            }
    except ImportError:
        pass

    try:
        import ultralytics
        report["ultralytics_available"] = True
    except ImportError:
        pass

    try:
        import face_recognition
        report["face_recognition_available"] = True
    except ImportError:
        pass

    try:
        import insightface
        report["insightface_available"] = True
    except ImportError:
        pass

    return report
