from pathlib import Path
import shutil

from .config import DestinationConfig


class DeliveryError(Exception):
    pass


class Transport:
    def deliver(self, source: Path, destination: DestinationConfig) -> None:
        raise NotImplementedError


class FilesystemTransport(Transport):
    def deliver(self, source: Path, destination: DestinationConfig) -> None:
        if not destination.remote_path:
            raise DeliveryError("filesystem destination remote_path is empty")
        target_dir = Path(destination.remote_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        temp = target.with_name(target.name + ".part")
        shutil.copyfile(source, temp)
        temp.replace(target)
        if destination.verify_remote_size and target.stat().st_size != source.stat().st_size:
            target.unlink(missing_ok=True)
            raise DeliveryError("filesystem transfer size verification failed")


class SFTPTransport(Transport):
    def deliver(self, source: Path, destination: DestinationConfig) -> None:
        try:
            import paramiko
        except ImportError as exc:
            raise DeliveryError("Paramiko is required for SFTP delivery") from exc
        if not destination.host or not destination.remote_path or not destination.username:
            raise DeliveryError("SFTP destination requires host, username and remote_path")
        if not destination.private_key_file:
            raise DeliveryError("SFTP private_key_file is not configured")

        remote_dir = destination.remote_path.rstrip("/")
        remote_file = f"{remote_dir}/{source.name}"
        ssh = paramiko.SSHClient()
        # Host-key policy is deliberately explicit: production should provide
        # a known_hosts policy rather than silently trusting a new host.
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            key = paramiko.RSAKey.from_private_key_file(destination.private_key_file)
            ssh.connect(
                hostname=destination.host,
                port=destination.port or 22,
                username=destination.username,
                pkey=key,
                timeout=destination.connect_timeout_seconds,
                banner_timeout=destination.connect_timeout_seconds,
                auth_timeout=destination.connect_timeout_seconds,
            )
            with ssh.open_sftp() as sftp:
                sftp.stat(remote_dir)
                temp = remote_file + ".part"
                sftp.put(str(source), temp)
                if destination.verify_remote_size and sftp.stat(temp).st_size != source.stat().st_size:
                    try:
                        sftp.remove(temp)
                    except OSError:
                        pass
                    raise DeliveryError("SFTP transfer size verification failed")
                sftp.rename(temp, remote_file)
        except DeliveryError:
            raise
        except Exception as exc:
            raise DeliveryError(f"SFTP delivery failed: {exc}") from exc
        finally:
            try:
                ssh.close()
            except Exception:
                pass


def transport_for(destination: DestinationConfig) -> Transport:
    if destination.protocol == "filesystem":
        return FilesystemTransport()
    if destination.protocol == "sftp":
        return SFTPTransport()
    raise DeliveryError(f"Unsupported delivery protocol: {destination.protocol}")
