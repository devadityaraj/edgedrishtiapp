"""
Platform-specific adaptations for Windows/Linux.
Handles path differences, process management, GPU detection.
"""

import platform
import os
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class PlatformAdapter:
    """Platform abstraction layer"""
    
    @staticmethod
    def get_os_type() -> str:
        """Get OS type"""
        return platform.system().lower()  
    
    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows"""
        return PlatformAdapter.get_os_type() == "windows"
    
    @staticmethod
    def is_linux() -> bool:
        """Check if running on Linux"""
        return PlatformAdapter.get_os_type() == "linux"
    
    @staticmethod
    def get_path_separator() -> str:
        """Get platform path separator"""
        return os.sep
    
    @staticmethod
    def get_home_dir() -> Path:
        """Get user home directory"""
        return Path.home()
    
    @staticmethod
    def get_app_data_dir() -> Path:
        """Get app data directory"""
        if PlatformAdapter.is_windows():
            
            appdata = os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))
            return Path(appdata) / "edge-drishti"
        else:
            
            return Path.home() / ".edge-drishti"
    
    @staticmethod
    def get_temp_dir() -> Path:
        """Get temporary directory"""
        import tempfile
        return Path(tempfile.gettempdir())
    
    @staticmethod
    def get_webcam_names() -> list:
        """
        Get available webcam device names.
        Windows: uses DirectShow
        Linux: uses /dev/video*
        """
        if PlatformAdapter.is_windows():
            try:
                import cv2
                webcams = []
                
                for i in range(10):
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        webcams.append(i)
                        cap.release()
                return webcams
            except Exception as e:
                logger.error(f"Error enumerating webcams: {e}")
                return []
        else:
            
            import glob
            return sorted(glob.glob("/dev/video*"))
    
    @staticmethod
    def get_environment_var(key: str, default: str = "") -> str:
        """Get environment variable"""
        return os.getenv(key, default)
    
    @staticmethod
    def set_environment_var(key: str, value: str) -> None:
        """Set environment variable"""
        os.environ[key] = value
    
    @staticmethod
    def get_gpu_info() -> Dict[str, any]:
        """
        Detect GPU and return device info.
        Returns info about NVIDIA, AMD, Intel, or CPU-only.
        """
        gpu_info = {
            "nvidia": False,
            "amd": False,
            "intel": False,
            "cpu_cores": os.cpu_count() or 1,
            "inference_device": "cpu"
        }
        
        # Try NVIDIA GPU (CUDA)
        try:
            import torch
            if torch.cuda.is_available():
                gpu_info["nvidia"] = True
                gpu_info["cuda_available"] = True
                gpu_info["cuda_devices"] = torch.cuda.device_count()
                gpu_info["cuda_version"] = torch.version.cuda
                gpu_info["inference_device"] = "cuda"
                logger.info(f"NVIDIA GPU detected: {gpu_info['cuda_devices']} device(s)")
        except Exception as e:
            logger.debug(f"CUDA check failed: {e}")
        
        # Try AMD GPU (ROCm) if no NVIDIA
        if not gpu_info["nvidia"]:
            try:
                import torch_directml
                if torch_directml.is_available():
                    gpu_info["amd"] = True
                    gpu_info["inference_device"] = "rocm"
                    logger.info("AMD GPU (ROCm) detected")
            except Exception as e:
                logger.debug(f"ROCm check failed: {e}")
        
        # Try Intel GPU (OpenVINO)
        if not gpu_info["nvidia"] and not gpu_info["amd"]:
            try:
                from openvino.runtime import Core
                ie = Core()
                available_devices = ie.available_devices
                if "GPU" in available_devices:
                    gpu_info["intel"] = True
                    gpu_info["inference_device"] = "openvino"
                    logger.info("Intel GPU (OpenVINO) detected")
            except Exception as e:
                logger.debug(f"OpenVINO check failed: {e}")
        
        return gpu_info
    
    @staticmethod
    def get_system_info() -> Dict[str, any]:
        """Get comprehensive system information"""
        import psutil
        
        return {
            "os": platform.system(),
            "os_version": platform.release(),
            "architecture": platform.architecture()[0],
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "total_memory_gb": psutil.virtual_memory().total / (1024**3),
            "disk_space_gb": psutil.disk_usage("/").total / (1024**3),
            "gpu_info": PlatformAdapter.get_gpu_info()
        }



platform_adapter = PlatformAdapter()
