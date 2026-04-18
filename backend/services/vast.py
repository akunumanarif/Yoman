import json
import logging
import subprocess
import time
from dataclasses import dataclass

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class InstanceInfo:
    id: int
    status: str
    ssh_host: str | None = None
    ssh_port: int | None = None


class VastService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.vast_api_key
        self._init_sdk()

    def _init_sdk(self):
        try:
            from vastai_sdk import VastAI
            self.client = VastAI(api_key=self.api_key)
        except ImportError:
            logger.warning("vastai_sdk not installed, using CLI fallback")
            self.client = None

    def search_offers(self) -> list[dict]:
        """Search for available interruptible GPU instances."""
        preferred = settings.gpu_preferred_models.split(",")
        min_vram = settings.gpu_min_vram

        query = f"gpu_ram>={min_vram} rented=False rentable=True"

        if self.client:
            result = self.client.search_offers(query=query)
            if isinstance(result, str):
                result = json.loads(result)
            return result if isinstance(result, list) else []

        # CLI fallback
        output = subprocess.run(
            ["vastai", "search", "offers", query, "--raw"],
            capture_output=True, text=True,
        )
        return json.loads(output.stdout) if output.returncode == 0 else []

    def find_cheapest_gpu(self) -> dict | None:
        """Find the cheapest suitable interruptible GPU offer."""
        offers = self.search_offers()
        if not offers:
            return None

        preferred = [m.strip() for m in settings.gpu_preferred_models.split(",")]

        # Filter by preferred GPU models
        filtered = [
            o for o in offers
            if any(p.lower() in o.get("gpu_name", "").lower() for p in preferred)
        ]

        if not filtered:
            filtered = offers

        # Sort by price (dph_total = dollars per hour total)
        filtered.sort(key=lambda o: o.get("dph_total", float("inf")))
        return filtered[0] if filtered else None

    def create_instance(self, offer_id: int, disk_gb: int = 100) -> int | None:
        """Create an interruptible instance from a specific offer."""
        docker_image = settings.vast_docker_image
        bid_price = settings.gpu_max_bid_price

        if self.client:
            try:
                result = self.client.create_instance(
                    ID=offer_id,
                    image=docker_image,
                    disk=disk_gb,
                    price=bid_price,
                )
                if isinstance(result, str):
                    result = json.loads(result)
                if isinstance(result, dict):
                    return result.get("new_contract") or result.get("id")
                logger.error(f"Unexpected create_instance result: {result}")
                return None
            except Exception as e:
                logger.error(f"SDK create_instance failed: {e}")

        # CLI fallback
        output = subprocess.run(
            [
                "vastai", "create", "instance", str(offer_id),
                "--image", docker_image,
                "--disk", str(disk_gb),
                "--price", str(bid_price),
                "--raw",
            ],
            capture_output=True, text=True,
        )
        if output.returncode == 0:
            data = json.loads(output.stdout)
            return data.get("new_contract")
        logger.error(f"Failed to create instance: {output.stderr}")
        return None

    def get_instance(self, instance_id: int) -> InstanceInfo | None:
        """Get instance status and connection details."""
        if self.client:
            result = self.client.show_instance(id=instance_id)
            if isinstance(result, str):
                result = json.loads(result)
        else:
            output = subprocess.run(
                ["vastai", "show", "instance", str(instance_id), "--raw"],
                capture_output=True, text=True,
            )
            if output.returncode != 0:
                return None
            result = json.loads(output.stdout)

        if not isinstance(result, dict):
            return None

        return InstanceInfo(
            id=instance_id,
            status=result.get("actual_status", "unknown"),
            ssh_host=result.get("ssh_host"),
            ssh_port=result.get("ssh_port"),
        )

    def wait_for_running(self, instance_id: int, timeout: int = 600) -> InstanceInfo | None:
        """Poll until instance is running or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            info = self.get_instance(instance_id)
            if info and info.status == "running":
                return info
            if info and info.status in ("exited", "error"):
                logger.error(f"Instance {instance_id} entered {info.status} state")
                return None
            time.sleep(15)
        logger.error(f"Instance {instance_id} timed out waiting for running state")
        return None

    def destroy_instance(self, instance_id: int):
        """Terminate and destroy an instance."""
        if self.client:
            self.client.destroy_instance(id=instance_id)
        else:
            subprocess.run(
                ["vastai", "destroy", "instance", str(instance_id)],
                capture_output=True, text=True,
            )
        logger.info(f"Destroyed instance {instance_id}")

    def get_ssh_command(self, instance_id: int) -> tuple[str, int] | None:
        """Get SSH connection details for an instance."""
        info = self.get_instance(instance_id)
        if info and info.ssh_host and info.ssh_port:
            return (info.ssh_host, info.ssh_port)
        return None
