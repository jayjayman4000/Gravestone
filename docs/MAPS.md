# Selectable offline county map packs

## What is implemented

Maps are selected by each user, not tied to the original owner's hometown. The bundled offline selector contains **3,222 county/equivalent entries across 52 U.S. state/territory codes**, from the archived Census catalog. It does not require a network connection merely to browse that catalog.

The initial regional format is **U.S. Census TIGER/Line 2025**:
- ROADS: road/highway/path centerlines with publisher names and MTFCC classifications.
- LINEARWATER: mapped linear-water geometry and names where supplied.
- The original ZIP, derived GeoJSON, source URL, SHA-256 values, year, extent, transformation and rights attribution are retained for each installed layer.

The renderer distinguishes major roads by line weight and water by dashed lines, labels source names, and supports pan, zoom and coordinate centering. All four interface palettes apply to its geometry. This is a reference line map: **no route calculation, live road/passability information, elevation, contours, satellite imagery, road directions, water-quality assessment or guaranteed complete street coverage**. Topography is disabled because it is not installed. The worldwide country-outline map remains a separate overview, not a substitute for regional roads.

## Use in the interface

1. Open **Maps**, then **Map tools & coverage**.
2. Select a state/territory and county. Choose roads and/or linear water.
3. While preparing on a connected machine, explicitly enable the online-preparation checkbox and choose **Download selected county layers**. No download occurs automatically on page load.
4. After completion, select **View county**, then **Back to map**. The map reads installed local geometry; internet is not needed afterward.
5. Installed-layer rows show actual storage use, source/byte-integrity details and an explicit Remove action with a confirmation prompt.

Only one county is selected for display at a time in this iteration. Multiple counties/layers can be stored. This is not yet a continuous, multi-county route-planning application or a global downloadable-map catalog.

## Preparing without networking on the live drive

The live image still disables automatic network configuration. A Download button does not enable Wi-Fi/Ethernet or override operating-system network policy. Prepare maps before an emergency, on a connected environment running the application, or use the offline import flow:

1. On a connected computer, acquire the original county ZIP from the fixed official Census source for the year/layer shown below.
2. Move that ZIP to a location accessible to the running archive. Ordinary USB/file selection stays under the user's control; Gravestone does not automatically mount internal disks or provision drives.
3. In Map tools select the matching state/county and import layer, select the original ZIP and choose **Import selected official Census ZIP (offline)**.
4. Import validates supported structure/projection/coordinates and computes byte digests, but **cannot authenticate the publisher origin of a user-supplied file**. Its metadata and source information explicitly identify that distinction.

Official URL forms, where `COUNTY` is the five-digit county/equivalent ID selected from the catalog:

```text
https://www2.census.gov/geo/tiger/TIGER2025/ROADS/tl_2025_COUNTY_roads.zip
https://www2.census.gov/geo/tiger/TIGER2025/LINEARWATER/tl_2025_COUNTY_linearwater.zip
```

A catalog entry is not proof that every corresponding layer URL is currently retrievable; failed requests are shown as errors and no partial layer is installed.

## Storage and persistence

Packs live under **`<configured data directory>/maps/`**, not the read-only source or content tree. Preserve this directory when preparing copies. The application does not establish reboot persistence: on a nonpersistent live session these downloads/imports are lost at shutdown just like notebook data. Provision and test the intended removable writable storage before relying on it.

Per-layer admission limits are 64 MiB compressed, 256 MiB declared ZIP contents, 96 MiB derived GeoJSON, 200,000 records and 2 million vertices. Installation reserves 512 MiB free plus conversion headroom. Original ZIPs and derived geometry both occupy space. Large counties may be rejected rather than silently truncated. Exact download size is unknown until the publisher responds; a 16 GB drive is not a promise of every U.S. region fitting.

## Backend and protections

- `GET /api/maps/catalog`: local selection catalog and provenance.
- `GET /api/maps/installed`: local installed metadata.
- `GET /api/maps/data?id=<county>-<layer>&layer=roads|water`: integrity-checked local GeoJSON.
- `POST /api/maps/download`: JSON `{region_id, layers, online_preparation:true}`; explicit opt-in and same-origin required.
- `GET /api/maps/jobs/<id>`: current-session job state. Jobs are not resumed across process restarts.
- `POST /api/maps/import?region_id=<county>&layer=<layer>`: `application/zip` original bytes, same-origin required.
- `POST /api/maps/remove`: JSON `{id}`; removes that explicitly identified pack.

Downloads use only generated official HTTPS Census URLs, with redirects refused, time/size bounds and no arbitrary caller URL. ZIP members are read without filesystem extraction; unexpected names, traversal, duplicates, symlinks, encrypted members, unsupported compression, missing shapefile components and unsupported projections are rejected. NAD83 geographic coordinates are retained without simplification. Installation keeps the validated maps-root descriptor open and anchors staging creation, no-follow file writes, publication, cleanup and synchronization to directory descriptors. It checks visible root identity before publication and uses Linux `renameat2(RENAME_NOREPLACE)`, failing closed when unsupported, so a concurrent layer cannot be silently overwritten. Removal is descriptor-relative too. Disposable regression tests replace the maps root or a writable-data ancestor during conversion/removal and verify that outside directories remain untouched. Conversion uses vendored **pyshp 2.3.1** with its original license and source provenance.

Census reuse evidence and catalog/download provenance are retained under `content/maps/`. This code does not imply Census endorsement or any separate right to use agency trademarks as application branding.

## Actual execution evidence

The interrupted implementation worker left working code and real District of Columbia road/water packs. Parent subsequently exercised the integrated browser workflow to select **Arlington County, VA (51013)** and download both official 2025 layers:
- Roads: 2,524 line features, 620,424 original ZIP bytes.
- Linear water: 32 features, 32,645 original ZIP bytes.
- Both original-file hashes matched their installed metadata; the local API returned matching feature counts and the browser visibly rendered named roads/highways and the water layer.
- Earlier DC packs contain 4,335 road features and 83 linear-water features; their local bytes/API counts were independently checked too.

These are QA packs under `/tmp/gravestone-map-qa-data`, **not automatically bundled regional coverage or updates to an existing flashed USB**. Durable screenshots and browser assertions are under `/home/jayjayman4000/gravestone-test-evidence/civilian-kiosk-integrated/`. Browser preview, download/import behavior, whole-image boot, physical hardware and reboot persistence are distinct test boundaries.
