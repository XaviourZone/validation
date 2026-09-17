# Offline Validation Bootstrap

The production Ubuntu machine does not need Internet access and does not need to download Python or Python packages.

On an Internet-connected Windows machine, run:
powershell -ExecutionPolicy Bypass -File .\Validation\bootstrap\prepare_offline_bundle.ps1

This prepares:
runtime/cpython-3.14.7+20260814-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz
offline_packages/*.whl

On the offline Ubuntu machine:
cd /path/to/Validation
chmod +x Validation/bootstrap/*.sh
./Validation/bootstrap/start_validation.sh

The bootstrap:
1. Checks Linux x86_64.
2. Installs bundled Python 3.14.7 if absent.
3. Skips Python installation if that exact bundled runtime is already present.
4. Creates .venv if absent.
5. Installs/updates dependencies only from offline_packages.
6. Validates Data Router configuration.
7. Starts Data Router, Data Parser, Data Forwarder and Web Console.

No apt, Internet, PyPI, or external API is used by the bootstrap.

The standalone runtime targets glibc 2.17 or newer, which covers Ubuntu 18.x systems using glibc 2.27. The host system Python remains untouched.
