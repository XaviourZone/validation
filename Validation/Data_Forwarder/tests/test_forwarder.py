from app.config import DestinationConfig, ForwarderConfig, RetryConfig, SpoolConfig
from app.service import ForwarderService
from app.secrets import SecretStore


def make_service(tmp_path, enabled=True):
    spool = SpoolConfig(
        tmp_path / "pending", tmp_path / "delivered", tmp_path / "failed",
        tmp_path / "state.db", tmp_path / "secrets.json", 0.01
    )
    dest_dir = tmp_path / "remote"
    dest = DestinationConfig("test", enabled=enabled, protocol="filesystem", remote_path=str(dest_dir), password_file=spool.secret_file)
    cfg = ForwarderConfig(tmp_path / "forwarder.yaml", "127.0.0.1", 0, tmp_path / "forwarder.yaml", spool, RetryConfig(max_attempts=2, initial_delay_seconds=0), {"test": dest})
    return ForwarderService(cfg)


def test_successful_delivery_and_archive(tmp_path):
    service = make_service(tmp_path)
    source = service.config.spool.input_dir / "SAIS_TEST_123.xml"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("<XTracks><XTrack/></XTracks>", encoding="utf-8")
    service.process_once()
    assert not source.exists()
    assert (tmp_path / "remote" / source.name).exists()
    assert list(service.config.spool.archive_dir.glob("*.xml"))
    assert service.state.counts()["DELIVERED"] == 1


def test_disabled_destination_keeps_pending(tmp_path):
    service = make_service(tmp_path, enabled=False)
    source = service.config.spool.input_dir / "one.xml"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("<XTracks/>", encoding="utf-8")
    service.process_once()
    assert source.exists()


def test_duplicate_delivery_is_not_repeated(tmp_path):
    service = make_service(tmp_path)
    source = service.config.spool.input_dir / "one.xml"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("<XTracks/>", encoding="utf-8")
    service.process_once()
    second = service.config.spool.input_dir / source.name
    second.write_text("<XTracks/>", encoding="utf-8")
    service.process_once()
    assert service.state.counts()["DELIVERED"] == 1


def test_secret_store_is_owner_only(tmp_path):
    store = SecretStore(tmp_path / "secrets.json")
    store.set("test", "secret-value")
    assert store.get("test") == "secret-value"
    assert store.has("test")
