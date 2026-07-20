"""
EDGE Drishti - System Monitor
Hardware monitoring, health checks, and resource management
"""

import psutil
import platform
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SystemHealth:
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    disk_free_gb: float
    temperature: Optional[float]
    uptime_seconds: int
    process_count: int
    is_healthy: bool
    warnings: list
    errors: list


class SystemMonitor:
    """Monitor system health and resource usage"""

    def __init__(self):
        self.boot_time = datetime.now()
        self.cpu_threshold = 90  
        self.memory_threshold = 85  
        self.disk_threshold = 90  
        self.temp_threshold = 85  # celsius (if available)

    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        try:
            return {
                "system": platform.system(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(logical=False),
                "cpu_count_logical": psutil.cpu_count(logical=True),
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {str(e)}")
            return {}

    def get_cpu_stats(self) -> Dict[str, Any]:
        """Get CPU statistics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_times = psutil.cpu_times_percent(interval=0)
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)

            return {
                "cpu_percent": cpu_percent,
                "cpu_times": {
                    "user": cpu_times.user,
                    "system": cpu_times.system,
                    "idle": cpu_times.idle,
                    "iowait": getattr(cpu_times, 'iowait', 0)
                },
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                },
                "cpu_count": psutil.cpu_count()
            }
        except Exception as e:
            logger.error(f"Failed to get CPU stats: {str(e)}")
            return {}

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        try:
            vm = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                "total_gb": vm.total / (1024 ** 3),
                "available_gb": vm.available / (1024 ** 3),
                "used_gb": vm.used / (1024 ** 3),
                "percent": vm.percent,
                "swap_total_gb": swap.total / (1024 ** 3),
                "swap_used_gb": swap.used / (1024 ** 3),
                "swap_percent": swap.percent
            }
        except Exception as e:
            logger.error(f"Failed to get memory stats: {str(e)}")
            return {}

    def get_disk_stats(self, path: str = "/") -> Dict[str, Any]:
        """Get disk statistics"""
        try:
            disk = psutil.disk_usage(path)

            return {
                "path": path,
                "total_gb": disk.total / (1024 ** 3),
                "used_gb": disk.used / (1024 ** 3),
                "free_gb": disk.free / (1024 ** 3),
                "percent": disk.percent
            }
        except Exception as e:
            logger.error(f"Failed to get disk stats: {str(e)}")
            return {}

    def get_process_stats(self) -> Dict[str, Any]:
        """Get process statistics"""
        try:
            process_count = len(psutil.pids())
            this_process = psutil.Process()

            return {
                "total_processes": process_count,
                "this_process": {
                    "pid": this_process.pid,
                    "name": this_process.name(),
                    "cpu_percent": this_process.cpu_percent(),
                    "memory_mb": this_process.memory_info().rss / (1024 ** 2),
                    "memory_percent": this_process.memory_percent(),
                    "num_threads": this_process.num_threads()
                }
            }
        except Exception as e:
            logger.error(f"Failed to get process stats: {str(e)}")
            return {}

    def get_temperature(self) -> Optional[Dict[str, Any]]:
        """Get system temperature (if available)"""
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None

            
            for name, entries in temps.items():
                if entries:
                    return {
                        "sensor": name,
                        "current": entries[0].current,
                        "high": entries[0].high,
                        "critical": entries[0].critical
                    }
            return None
        except Exception as e:
            logger.debug(f"Temperature data not available: {str(e)}")
            return None

    def get_network_stats(self) -> Dict[str, Any]:
        """Get network interface statistics"""
        try:
            net_if_stats = psutil.net_if_stats()
            net_io_counters = psutil.net_io_counters()

            interfaces = {}
            for interface, stats in net_if_stats.items():
                interfaces[interface] = {
                    "is_up": stats.isup,
                    "speed": stats.speed,
                    "mtu": stats.mtu
                }

            return {
                "interfaces": interfaces,
                "bytes_sent": net_io_counters.bytes_sent,
                "bytes_recv": net_io_counters.bytes_recv,
                "packets_sent": net_io_counters.packets_sent,
                "packets_recv": net_io_counters.packets_recv,
                "errin": net_io_counters.errin,
                "errout": net_io_counters.errout
            }
        except Exception as e:
            logger.error(f"Failed to get network stats: {str(e)}")
            return {}

    def get_uptime(self) -> Dict[str, Any]:
        """Get system uptime"""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            uptime_seconds = uptime.total_seconds()

            return {
                "boot_time": boot_time.isoformat(),
                "uptime_seconds": int(uptime_seconds),
                "uptime_formatted": self._format_uptime(uptime_seconds)
            }
        except Exception as e:
            logger.error(f"Failed to get uptime: {str(e)}")
            return {}

    def get_health_check(self) -> SystemHealth:
        """Comprehensive system health check"""
        try:
            cpu_stats = self.get_cpu_stats()
            memory_stats = self.get_memory_stats()
            disk_stats = self.get_disk_stats()
            uptime_stats = self.get_uptime()
            process_stats = self.get_process_stats()
            temp = self.get_temperature()

            cpu_percent = cpu_stats.get("cpu_percent", 0)
            memory_percent = memory_stats.get("percent", 0)
            disk_percent = disk_stats.get("percent", 0)
            disk_free_gb = disk_stats.get("free_gb", 0)
            uptime_seconds = uptime_stats.get("uptime_seconds", 0)
            process_count = process_stats.get("total_processes", 0)

            warnings = []
            errors = []

            
            if cpu_percent > self.cpu_threshold:
                warnings.append(f"High CPU usage: {cpu_percent}%")
            if memory_percent > self.memory_threshold:
                warnings.append(f"High memory usage: {memory_percent}%")
            if disk_percent > self.disk_threshold:
                errors.append(f"Low disk space: {disk_percent}% used ({disk_free_gb:.1f}GB free)")
            if disk_free_gb < 5:
                errors.append(f"Critical disk space: {disk_free_gb:.1f}GB remaining")

            if temp and temp.get("current", 0) > self.temp_threshold:
                warnings.append(f"High temperature: {temp['current']}°C")

            is_healthy = len(errors) == 0 and len(warnings) < 2

            return SystemHealth(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                disk_free_gb=disk_free_gb,
                temperature=temp.get("current") if temp else None,
                uptime_seconds=uptime_seconds,
                process_count=process_count,
                is_healthy=is_healthy,
                warnings=warnings,
                errors=errors
            )
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return SystemHealth(
                cpu_percent=0,
                memory_percent=0,
                disk_percent=0,
                disk_free_gb=0,
                temperature=None,
                uptime_seconds=0,
                process_count=0,
                is_healthy=False,
                warnings=[],
                errors=[str(e)]
            )

    def get_full_status(self) -> Dict[str, Any]:
        """Get complete system status"""
        health = self.get_health_check()

        return {
            "timestamp": datetime.now().isoformat(),
            "system_info": self.get_system_info(),
            "cpu": self.get_cpu_stats(),
            "memory": self.get_memory_stats(),
            "disk": self.get_disk_stats(),
            "network": self.get_network_stats(),
            "uptime": self.get_uptime(),
            "process": self.get_process_stats(),
            "temperature": self.get_temperature(),
            "health": {
                "is_healthy": health.is_healthy,
                "warnings": health.warnings,
                "errors": health.errors
            }
        }

    @staticmethod
    def _format_uptime(seconds: int) -> str:
        """Format uptime as human-readable string"""
        days = seconds // (24 * 3600)
        seconds = seconds % (24 * 3600)
        hours = seconds // 3600
        seconds = seconds % 3600
        minutes = seconds // 60
        seconds = seconds % 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)



system_monitor = SystemMonitor()
