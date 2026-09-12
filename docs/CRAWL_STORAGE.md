# Crawl storage

The crawler has two different storage workloads. They should not be treated as
one directory:

1. **Active database and workspace** — SQLite today, PostgreSQL/PostGIS later.
   This needs low-latency random reads/writes and a normal filesystem.
2. **Raw source archive** — compressed snapshots exactly as publishers served
   them. This needs inexpensive capacity, checksums, retention and off-site
   durability.

Object storage is suitable for the raw archive. It is not a filesystem and must
not contain the live SQLite database or its WAL files.

## Recommended first deployment

Use an encrypted APFS external SSD as the working store:

```text
/Volumes/PDA_DATA/
  registry/registry.sqlite
  raw/brreg/
  staging/
```

Run the first complete copy with both paths on that volume:

```bash
pda mirror-brreg enheter snapshot \
  --db /Volumes/PDA_DATA/registry/registry.sqlite \
  --storage-dir /Volumes/PDA_DATA/raw/brreg

pda mirror-brreg enheter updates \
  --db /Volumes/PDA_DATA/registry/registry.sqlite
```

Repeat for `underenheter`. Do not disconnect the volume while SQLite is open.
APFS (Encrypted) is preferred for a Mac-only drive. ExFAT is portable but does
not provide the same filesystem behavior or encryption for an active database.

The snapshot command checks capacity after its `HEAD` request and before it
downloads anything. For a complete import it reserves the compressed object,
512 MiB of raw-file headroom, an estimated 12 times the compressed size for
expanded SQLite rows and transaction state, and 1 GiB of database headroom. If
the database and raw directory share a filesystem, those requirements are
combined. A missing source `Content-Length` is rejected because the command
cannot make a safe estimate.

## Recommended cloud layer

Create one private S3-compatible bucket restricted to the EU jurisdiction, for
example `pda-raw-no`. Upload only completed raw objects and a small manifest:

```text
brreg/enheter/YYYY/MM/DD/<sha256>.csv.gz
brreg/underenheter/YYYY/MM/DD/<sha256>.csv.gz
manifests/brreg/YYYY/MM/DD/<snapshot-id>.json
```

Use a bucket-scoped token that can write/read objects but cannot administer the
account. Put credentials in the environment or operating-system keychain, never
in this repository. Enable object versioning or retention, lifecycle old daily
copies to a cheaper class, and keep at least one recent local snapshot for fast
recovery.

Cloudflare R2 is a straightforward starting option because it is S3-compatible,
supports an EU jurisdiction and does not charge Internet egress. Backblaze B2 or
AWS S3 also fit the interface. Provider choice should remain configuration, not
application logic.

## Retention proposal

- Keep the latest 7 daily snapshots locally.
- Keep 30 daily snapshots in object storage.
- Keep one monthly snapshot indefinitely until data-volume growth is understood.
- Keep every manifest, hash and crawl checkpoint; these are tiny.
- Never remove the last known-good snapshot during the same job that creates its
  replacement.

## Scale path

SQLite is appropriate for proving the first complete mirrors on one machine.
Move normalized records and crawl state to PostgreSQL/PostGIS before concurrent
workers, remote query serving or multi-terabyte geospatial ingestion. Raw bytes
remain in object storage under content-addressed keys, so changing the database
does not require redownloading the country.

## Provider references checked 2026-09-08

- Cloudflare R2 pricing: <https://developers.cloudflare.com/r2/pricing/>
- Cloudflare R2 EU jurisdiction: <https://developers.cloudflare.com/r2/reference/data-location/>
- Cloudflare R2 S3 compatibility: <https://developers.cloudflare.com/r2/how-r2-works/>
- Apple filesystem format guidance: <https://support.apple.com/guide/disk-utility/file-system-formats-dsku19ed921c/mac>
