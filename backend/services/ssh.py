import logging
import os
from pathlib import Path

import paramiko
from scp import SCPClient

logger = logging.getLogger(__name__)


class SSHService:
    """SSH/SCP service for communicating with vast.ai GPU instances."""

    def __init__(self, host: str, port: int, username: str = "root", key_path: str | None = None):
        self.host = host
        self.port = port
        self.username = username
        self.key_path = key_path or os.path.expanduser("~/.ssh/id_rsa")
        self._client: paramiko.SSHClient | None = None

    def connect(self):
        """Establish SSH connection."""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            key_filename=self.key_path,
            timeout=30,
        )
        logger.info(f"SSH connected to {self.host}:{self.port}")

    def close(self):
        """Close SSH connection."""
        if self._client:
            self._client.close()
            self._client = None

    @property
    def client(self) -> paramiko.SSHClient:
        if not self._client:
            self.connect()
        return self._client

    def execute(self, command: str, timeout: int = 3600) -> tuple[str, str, int]:
        """Execute a command on the remote instance. Returns (stdout, stderr, exit_code)."""
        logger.info(f"SSH exec: {command[:100]}...")
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode()
        err = stderr.read().decode()
        if exit_code != 0:
            logger.warning(f"Command exited with code {exit_code}: {err[:200]}")
        return out, err, exit_code

    def upload(self, local_path: str, remote_path: str):
        """Upload a file via SCP."""
        logger.info(f"SCP upload: {local_path} -> {remote_path}")
        with SCPClient(self.client.get_transport()) as scp:
            scp.put(local_path, remote_path)

    def download(self, remote_path: str, local_path: str):
        """Download a file via SCP."""
        logger.info(f"SCP download: {remote_path} -> {local_path}")
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        with SCPClient(self.client.get_transport()) as scp:
            scp.get(remote_path, local_path)

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the remote instance."""
        _, _, exit_code = self.execute(f"test -f {remote_path}")
        return exit_code == 0

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
