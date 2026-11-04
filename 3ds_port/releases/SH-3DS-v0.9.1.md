# SH-3DS v0.9.1

- Game source commit: `b047017a6`.
- Game Source ID: `SH1-New3DS-v0.9.0-src-284564170a9`.
- `SH-3DS-v0.9.1.3dsx`: 3,555,676 bytes; SHA-256 `3d7321870374a0a3d4201c5043f701de0800925bab84ec838711b84c93958d6b`.
- `SH-3DS-v0.9.1.cia`: 2,507,200 bytes; SHA-256 `23e5e20da8293aa7bfef2b8b0e5e1665faa92bf89fb7dc366580a17992a1b3c1`.

The 3DSX is the exact hardware-tested file. The CIA contains the corresponding
ELF, with HOME Menu title `SH-3DS` and the supplied banner audio. Its Title ID
remains `000400000F53D190` and its TMD version is 145. The verified 3DSX keeps
its original embedded title and pause-screen text at the user's request.

Packaging verification checks all HOME Menu locales, banner PCM, code against
the ELF's loadable segments, container hashes and hardware service permissions.
