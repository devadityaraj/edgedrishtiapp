"""
mDNS (Multicast DNS) service for EDGE Drishti.

Broadcasts TWO hostnames on the local network while the app is running:

  edgedrishti.local        → LAN IP   (user + admin portal, network-accessible)
  edgedrishti-admin.local  → 127.0.0.1 (master admin portal, loopback-only)

The loopback binding of edgedrishti-admin.local means network clients cannot
physically reach that name — the OS will not route 127.x.x.x off-machine.
No IP-list trickery is needed; the network topology enforces isolation.

When the app stops, both broadcasts stop — zero system footprint.
Works fully offline without internet.
"""

import socket
import logging
from typing import Optional

logger = logging.getLogger(__name__)


MDNS_USER_HOSTNAME  = "edgedrishti"               # → LAN IP  (user/admin portal)
MDNS_ADMIN_HOSTNAME = "edgedrishti-admin"          # → 127.0.0.1 (master admin only)

MDNS_USER_FQDN  = f"{MDNS_USER_HOSTNAME}.local."
MDNS_ADMIN_FQDN = f"{MDNS_ADMIN_HOSTNAME}.local."


LOOPBACK_IP = "127.0.0.1"


def _get_lan_ip() -> str:
    """
    Detect the machine's LAN IP address.
    Falls back to 127.0.0.1 if no network interface is found.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("10.255.255.255", 1))  
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class MDNSService:
    """
    Broadcasts TWO mDNS entries:
      - edgedrishti.local       → LAN IP   (user/admin portal)
      - edgedrishti-admin.local → 127.0.0.1 (master admin, localhost-only)

    Usage:
        mdns = MDNSService(port=8443)
        mdns.start()   # begins broadcasting both names
        ...
        mdns.stop()    # stops broadcasting, zero traces left
    """

    def __init__(self, port: int = 8443):
        self.port = port
        self._zeroconf = None
        self._user_info = None   
        self._admin_info = None  
        self._running = False

    def start(self) -> None:
        try:
            from zeroconf import Zeroconf, ServiceInfo
            import time

            self._running = True
            last_lan_ip = None

            while self._running:
                current_lan_ip = _get_lan_ip()
                if current_lan_ip != last_lan_ip:
                    if self._zeroconf and self._user_info:
                        try:
                            self._zeroconf.unregister_service(self._user_info)
                        except Exception:
                            pass

                    if not self._zeroconf:
                        try:
                            self._zeroconf = Zeroconf()
                        except Exception:
                            time.sleep(10)
                            continue

                    try:
                        lan_ip_bytes = socket.inet_aton(current_lan_ip)
                        self._user_info = ServiceInfo(
                            type_="_https._tcp.local.",
                            name="EDGE Drishti._https._tcp.local.",
                            addresses=[lan_ip_bytes],
                            port=self.port,
                            properties={
                                "path": "/",
                                "product": "EDGE Drishti Security Platform",
                                "portal": "user+admin",
                            },
                            server=MDNS_USER_FQDN,
                        )
                        self._zeroconf.register_service(self._user_info, allow_name_change=True)
                        logger.info(f"mDNS: 'edgedrishti.local'       → {current_lan_ip}:{self.port}  (user/admin portal)")
                        last_lan_ip = current_lan_ip
                    except Exception:
                        logger.exception("Failed to register mDNS user service")

                    if not self._admin_info:
                        try:
                            loopback_ip_bytes = socket.inet_aton(LOOPBACK_IP)
                            self._admin_info = ServiceInfo(
                                type_="_https._tcp.local.",
                                name="EDGE Drishti Admin._https._tcp.local.",
                                addresses=[loopback_ip_bytes],
                                port=self.port,
                                properties={
                                    "path": "/master-admin/",
                                    "product": "EDGE Drishti Master Admin Console",
                                    "portal": "master-admin",
                                    "restricted": "localhost-only",
                                },
                                server=MDNS_ADMIN_FQDN,
                            )
                            self._zeroconf.register_service(self._admin_info, allow_name_change=True)
                            logger.info(f"mDNS: 'edgedrishti-admin.local'  → {LOOPBACK_IP}:{self.port}  (master admin — localhost only)")
                        except Exception:
                            logger.exception("Failed to register mDNS admin service")

                time.sleep(10)

        except ImportError:
            logger.warning(
                "zeroconf not installed — mDNS disabled. "
                "Install with: pip install zeroconf"
            )
        except Exception:
            logger.exception("mDNS registration failed (app still works on IP)")

    def stop(self) -> None:
        """Unregister both mDNS services — leaves zero traces on the system."""
        if self._zeroconf:
            for info in [self._user_info, self._admin_info]:
                if info:
                    try:
                        self._zeroconf.unregister_service(info)
                    except Exception as e:
                        logger.warning(f"mDNS unregister error: {e}")
            try:
                self._zeroconf.close()
            except Exception as e:
                logger.warning(f"mDNS close error: {e}")

        self._zeroconf = None
        self._user_info = None
        self._admin_info = None
        self._running = False
        logger.info("mDNS: Both services unregistered — names removed from network")

    @property
    def is_running(self) -> bool:
        return self._running



mdns_service = MDNSService()
