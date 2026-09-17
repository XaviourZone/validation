"""Set a Forwarder destination password without putting it in Git/YAML."""

import argparse
import getpass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Validation.Data_Forwarder.app.secrets import SecretStore


def main():
    parser = argparse.ArgumentParser(description="Set a local Forwarder destination password")
    parser.add_argument("destination", nargs="?", default="D-DIODE-01")
    parser.add_argument("--secret-file", default="Validation/Data_Forwarder/state/forwarder_secrets.json")
    args = parser.parse_args()

    first = getpass.getpass(f"Password for {args.destination}: ")
    second = getpass.getpass("Confirm password: ")
    if not first:
        raise SystemExit("Password must not be empty.")
    if first != second:
        raise SystemExit("Passwords do not match.")

    path = Path(args.secret_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    SecretStore(path).set(args.destination, first)
    print(f"Password stored locally for {args.destination}: {path}")
    print("The password is not written to forwarder.yaml or source control.")


if __name__ == "__main__":
    main()
