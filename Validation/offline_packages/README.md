# Offline Python Package Cache

Populate this directory on an Internet-connected Windows machine with:
Validation/bootstrap/prepare_offline_bundle.ps1

The cache contains Linux x86_64 CPython 3.14 wheels and transitive dependencies.

The offline Ubuntu machine uses:
pip install --no-index --find-links=Validation/offline_packages

Do not place Windows wheels in this directory.
