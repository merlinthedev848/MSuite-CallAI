import logging
import aiohttp
from typing import Dict, Any, Optional
from config import config

logger = logging.getLogger("phone_agent.yeastar")

class YeastarS100Client:
    """
    Client interface for Yeastar S-Series (S100, S50, S20, S300) and P-Series PBX systems.
    Supports Click-to-Dial originating, extension status monitoring, and call transfer.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 8088,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_https: bool = True
    ):
        self.host = host or getattr(config, "yeastar_host", "192.168.1.100")
        self.port = port
        self.username = username or getattr(config, "yeastar_username", "api_user")
        self.password = password or getattr(config, "yeastar_password", "api_pass")
        self.use_https = use_https
        self.token: Optional[str] = None
        self.simulated_mode = not bool(host and username and password)

    @property
    def base_url(self) -> str:
        protocol = "https" if self.use_https else "http"
        return f"{protocol}://{self.host}:{self.port}/api/v1.1.0"

    async def login(self) -> bool:
        """Authenticates with Yeastar S-Series API and obtains access token."""
        if self.simulated_mode:
            logger.info("Yeastar PBX in simulated dev mode (no hardware IP configured).")
            self.token = "simulated_yeastar_token_12345"
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
                            logger.info(f"Successfully authenticated with Yeastar S100 at {self.host}")
                            return True
                    logger.warning(f"Yeastar authentication failed: {await resp.text()}")
                    return False
        except Exception as e:
            logger.warning(f"Could not connect to Yeastar S100 PBX at {self.host}: {e}. Operating in simulated mode.")
            self.simulated_mode = True
            return False

    async def originate_call(self, desk_extension: str, destination_phone: str) -> Dict[str, Any]:
        """
        Click-to-Dial: Rings the employee's desk phone (or Linkus app) first.
        Once the handset is lifted, Yeastar dials the customer's phone number.
        """
        logger.info(f"Click-to-Dial triggered: Staff ext {desk_extension} -> Customer {destination_phone}")

        if self.simulated_mode:
            return {
                "success": True,
                "status": "Success",
                "message": f"Simulated call initiated: Extension {desk_extension} will ring, then connect to {destination_phone} via Yeastar S100.",
                "call_id": f"sim-call-{desk_extension}-{destination_phone}"
            }

        if not self.token:
            await self.login()

        url = f"{self.base_url}/call/dial?token={self.token}"
        payload = {
            "extid": desk_extension,
            "outbound": destination_phone,
            "autoanswer": "yes"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, ssl=False, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    data = await resp.json()
                    return {
                        "success": data.get("status") == "Success",
                        "status": data.get("status"),
                        "message": data.get("status"),
                        "raw": data
                    }
        except Exception as e:
            logger.error(f"Failed to originate call on Yeastar PBX: {e}")
            return {"success": False, "error": str(e)}

    async def get_extension_status(self, extension: str) -> Dict[str, Any]:
        """Checks whether a Yeastar extension is currently Idle, Ringing, or In-Use."""
        if self.simulated_mode:
            return {
                "extension": extension,
                "status": "Idle",
                "simulated": True
            }

        if not self.token:
            await self.login()

        url = f"{self.base_url}/extension/query?token={self.token}&extid={extension}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    return data
        except Exception as e:
            return {"extension": extension, "status": "Unknown", "error": str(e)}


yeastar_client = YeastarS100Client()
