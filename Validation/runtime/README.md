# Validation Project Python Runtime

Target runtime:
- CPython 3.14.7
- Linux x86_64
- glibc-linked standalone distribution
- python-build-standalone release 20260814

Prepare the actual runtime archive on an Internet-connected machine with:
Validation/bootstrap/prepare_offline_bundle.ps1

The archive is intentionally not committed to Git because it is a large binary deployment artifact. Transfer it with the complete Validation project to the air-gapped Ubuntu host.

Do not replace /usr/bin/python3 on Ubuntu 18.x. Validation uses its own project-local runtime.
