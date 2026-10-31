# Notebook and installed-map backup / recovery

This is an **unencrypted**, bounded data backup, not a bootable USB clone, disk
image, browser-profile export, or full-system backup. Protect it like the private
notebook: anyone holding the archive can read notes and regional selections.
SHA-256 detects accidental corruption; it is **not authentication** against someone
who can rewrite both the data and its manifest. Keep an independent trusted copy
or externally recorded archive digest.

## CLI (Python standard library only; Linux)

Stop the dashboard and any map preparation job before exporting. The CLI does
not coordinate with the running application's locks. It refuses changing files
and inconsistent map hashes, but it cannot promise a simultaneous snapshot of
independently edited files.

```sh
# Example paths: substitute your own external writable directories.
python3 scripts/gravestone-backup.py export \
  --data-dir /path/to/existing-data \
  --archive /path/to/backup-storage/notebook-maps-001.tar

# The target's PARENT must already exist; the target itself MUST NOT exist.
python3 scripts/gravestone-backup.py restore \
  --archive /path/to/backup-storage/notebook-maps-001.tar \
  --data-dir /path/to/scratch/new-recovered-data

# Inspect the recovered notebook and map selection before using the new directory.
python3 -m app --data-dir /path/to/scratch/new-recovered-data \
  --host 127.0.0.1 --port 0
```

`python3 -m app.backup` accepts the same arguments. Success prints a schema-1 JSON
manifest; refusals print a reason to stderr and exit nonzero. The encryption
warning is always printed. There is no `--force` or replace/merge option. Export
refuses an existing archive, including symlinks. Restore refuses **any** existing
target, even an empty directory. It never replaces existing notes or packs.
The selected data directory must be separate from the checkout/content tree when
starting the application. All implemented acceptance checks used scratch data
outside the checkout, never a user's real notebook.

## What is preserved

Only these exact regular-file names are eligible:

- `notes.txt` (optional; saved bytes, not the unsaved browser draft).
- `maps/NNNNN-roads/{metadata.json,data.geojson,original.zip}`.
- `maps/NNNNN-water/{metadata.json,data.geojson,original.zip}`.

Every included pack must contain all three files; its metadata ID and original /
geometry SHA-256 values must match. Unexpected files are **never** included.
Firefox profiles, passwords, shell configuration, repositories, library PDFs,
models, cache files, and unrelated data are not recursively copied. Notes and map
metadata may themselves contain sensitive user information; the tool cannot
sanitize their contents without breaking byte preservation.

The archive is an uncompressed USTAR containing a `manifest.json` with schema 1,
exact allowlisted file paths, byte lengths and SHA-256 digests. Directories are
recreated, not extracted. Permissions are private: files `0600`, directories
`0700`. Original timestamps, ownership and permissions are not restored.

Hard limits (refuse the whole operation, never silently omit an oversized pack):

| Bound | Limit |
|---|---:|
| Archive input/output | 50 MiB |
| Combined data bytes | 48 MiB |
| Individual ZIP / GeoJSON file | 32 MiB |
| Notebook | 256 KiB |
| Pack metadata | 32 KiB |
| Manifest | 512 KiB |
| Data files / enumerated map entries | 1,000 each |

Large counties or many installed regions can exceed this deliberately small
first-version limit. There is no partial-success backup mode or compressed format.
The original Census ZIP is treated as a bounded opaque file during recovery;
recovery does not expand it or download anything.

## Safety / failure behavior

All archive bytes, schema, exact file inventory, lengths and hashes are checked
**before creating restore staging**. Absolute paths, traversal, backslashes,
noncanonical/NUL-hidden names, duplicate names/JSON keys, unknown schema/fields,
missing/unmanifested data, incomplete packs, bad headers/padding/truncation,
compressed input, oversized entries, sparse files, symlinks, hardlinks, devices,
FIFOs, directory entries, PAX/GNU extension entries and nonregular members are
rejected. Export also refuses symlink/hardlink/nonregular allowlisted inputs.

Source/target ancestors are walked with `open_root` and no-follow directory
opens. Reads, creation, fsync, publication and rollback remain relative to open
directory descriptors; a replaced ancestor does not redirect writes/deletions
through a newly inserted symlink. Temporary entry identity and visible parent
identity are checked before publication. Linux `renameat2(RENAME_NOREPLACE)`
publishes one complete directory/archive atomically and refuses a concurrent
new target. Filesystems lacking that primitive fail closed. Do not place working
or backup directories in locations writable by untrusted users; these controls
are not protection from a malicious process with the same UID/root privileges.

A failure before publication removes tool-owned staging through the pinned
filesystem descriptors. A directory maliciously moved by a different process may
remain at that process's chosen name; cleanup does not follow substituted links.
If parent-directory fsync fails **after** atomic publication, the CLI reports a
failure but retains the verified published bytes rather than erasing them.
Inspect the target before retrying. This reports uncertain power-loss durability,
not an incomplete snapshot. A power cut can also leave private `.backup-*` or
`.restore-*` staging: inspect scratch storage while the application is stopped;
never treat temporary names as a successful backup.

## Reproducible checks

```sh
python3 -m unittest discover -s tests -p test_backup.py -v
python3 -m unittest discover -s tests -p test_maps_recovery.py -v
# Explicit ONLINE preparation; then network-guarded child-server HTTP checks:
GRAVESTONE_REAL_MAP_RECOVERY=1 \
  python3 -m unittest discover -s tests -p test_maps_recovery.py -v
python3 -m unittest discover -s tests -v
```

The opt-in test downloads **real official 2025 Census Arlington County, VA
(51013)** roads and linear-water ZIPs through `app.maps.download`'s fixed-origin,
no-redirect code. The total download batch is capped at 50 MiB. Publisher originals
and JSON provenance/results remain outside the checkout in:

`/home/jayjayman4000/gravestone-test-evidence/map-backup-recovery/`

`latest-result.json` points to the actual archive/original files and records each
phase, subprocess PID/ephemeral port, source hashes, metadata, feature counts,
HTTP geometry equality and exact before/after hashes for notes plus every pack
file. Each run has its own `official-arlington-*` directory and `result.json`.

The test creates three separate Python server processes on loopback port 0:
install/save, restart from existing scratch data, then start with a new recovered
data directory. It exercises `/api/notes`, `/api/maps/installed` and
`/api/maps/data` over real HTTP. The fixture test does the same without downloads.
Each child self-tests raising guards on map download, urllib HTTP and
non-loopback socket connections; those guards stay active for the HTTP checks.
**This is Python-level network denial, not physical disconnection or kernel
network-namespace isolation.** Rootless `unshare -Urn` was denied by this host.

Actual official-data exercise: 2,524 road features and 32 linear-water features
survived process restart and exact-byte backup/recovery. These are reference line
maps only: **no computed routing, passability, water potability, elevation or
comprehensive coverage is established**.

## Still required on the physical appliance

Application process restart is not a USB reboot, power-loss test, filesystem
repair test or a verified persistence configuration. Before relying on this:

1. Confirm the notebook/maps directory is on the intended writable persistent
   removable volume, not the live session's temporary overlay or a host disk.
2. Save a harmless scratch marker, install a test regional pack, shut down cleanly,
   and perform two actual USB reboot checks with networking disconnected.
3. Confirm the marker, pack hashes, installed metadata and usable geometry after
   both boots, then recover a separately stored backup into a new scratch directory.
4. Verify in the shipped Firefox/live image and on the intended hardware.

No physical reboot, USB provisioning, live-image rebuild, shared-service restart
or actual personal-notebook migration was performed for these checks.
