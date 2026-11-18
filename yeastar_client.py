import re
import logging
import aiohttp
from typing import Dict, Any, Optional
from config import config

logger = logging.getLogger("phone_agent.yeastar")


class YeastarS100Client:
    """
    Robust API Client for Yeastar S-Series (S100, S50, S20, S300) and P-Series PBXs.
    Handles token authentication, automatic session refresh, Click-to-Dial originating,
    and extension presence querying.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_https: bool = True
    ):
        self.host = host or config.yeastar_host
        self.port = port or config.yeastar_port
        self.username = username or config.yeastar_username
        self.password = password or config.yeastar_password
        self.use_https = use_https
        self.token: Optional[str] = None
        # Simulated mode if no physical credentials or host is default dummy
        self.simulated_mode = not bool(self.password and self.password != "api_pass")

    @property
    def base_url(self) -> str:
        protocol = "https" if self.use_https else "http"
        return f"{protocol}://{self.host}:{self.port}/api/v1.1.0"

    def _sanitize_phone(self, phone: str) -> str:
        """Strips non-dialable characters while preserving leading '+'."""
        clean = re.sub(r"[^\d+]", "", phone.strip())
        if config.yeastar_outbound_prefix and not clean.startswith(config.yeastar_outbound_prefix):
            clean = f"{config.yeastar_outbound_prefix}{clean}"
        return clean

    def _sanitize_extension(self, ext: str) -> str:
        """Ensures extension contains only digits."""
        return re.sub(r"\D", "", ext.strip())

    async def login(self) -> bool:
        """Authenticates with Yeastar PBX and stores access token."""
        if self.simulated_mode:
            logger.info("Yeastar PBX in simulated dev mode (live hardware IP not configured).")
            self.token = "simulated_yeastar_token_valid"
            return True

        url = f"{self.base_url}/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "version": "1.1.0"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, ssl=False, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "Success":
                            self.token = data.get("token")
                            logger.info(f"Authenticated with Yeastar S100 at {self.host}")
                            return True
                    text = await resp.text()
                    logger.warning(f"Yeastar login failed: {text}")
                    return False
        except Exception as e:
            logger.warning(f"Yeastar PBX unreachable at {self.host}: {e}. Operating in simulated mode.")
            self.simulated_mode = True
            self.token = "simulated_yeastar_token_fallback"
            return False

    async def originate_call(self, desk_extension: str, destination_phone: str) -> Dict[str, Any]:
        """
        Click-to-Dial via Yeastar S100:
        Rings the staff member's desk extension. When picked up, dials the customer.
        """
        clean_ext = self._sanitize_extension(desk_extension)
        clean_dest = self._sanitize_phone(destination_phone)

        if not clean_ext:
            return {"success": False, "error": "Invalid staff extension format"}
        if not clean_dest:
            return {"success": False, "error": "Invalid destination phone format"}

        logger.info(f"Yeastar Click-to-Dial: Ext {clean_ext} -> Destination {clean_dest}")

        if self.simulated_mode:
            return {
                "success": True,
                "status": "Success",
                "message": f"Simulated call dispatched: Extension {clean_ext} will ring and connect to {clean_dest}.",
                "extension": clean_ext,
                "destination": clean_dest,
                "simulated": True
            }

        if not self.token:
            await self.login()

        url = f"{self.base_url}/call/dial?token={self.token}"
        payload = {
            "extid": clean_ext,
            "outbound": clean_dest,
            "autoanswer": "yes"
        }

        for attempt in range(2):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, ssl=False, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        data = await resp.json()
                        # If token expired (error code 10003 in Yeastar)
                        if data.get("status") == "Failed" and "token" in str(data.get("errno", "")).lower():
                            logger.info("Yeastar token expired. Re-authenticating...")
                            await self.login()
                            url = f"{self.base_url}/call/dial?token={self.token}"
                            continue

                        is_success = data.get("status") == "Success"
                        return {
                            "success": is_success,
                            "status": data.get("status"),
                            "message": data.get("status"),
                            "extension": clean_ext,
                            "destination": clean_dest,
                            "raw": data
                        }
            except Exception as e:
                logger.error(f"Yeastar originate error on attempt {attempt+1}: {e}")
                if attempt == 0:
                    await self.login()
                else:
                    return {"success": False, "error": str(e)}

        return {"success": False, "error": "Failed to initiate call after retry"}

    async def get_extension_status(self, extension: str) -> Dict[str, Any]:
        """Queries the current presence/state of a Yeastar extension."""
        clean_ext = self._sanitize_extension(extension)

        if self.simulated_mode:
            return {
                "extension": clean_ext,
                "status": "Idle",
                "simulated": True
            }

        if not self.token:
            await self.login()

        url = f"{self.base_url}/extension/query?token={self.token}&extid={clean_ext}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    return data
        except Exception as e:
            return {"extension": clean_ext, "status": "Unknown", "error": str(e)}


yeastar_client = YeastarS100Client()
