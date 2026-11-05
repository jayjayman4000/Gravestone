# Source preservation policy

This document describes editorial and technical controls, not emergency procedures.

## Layers

1. **Publisher originals**: authoritative archived source files; retain original bytes.
2. **Search derivatives**: mechanically extracted text for discovery only; explicitly unverified unless checked against the original page. Never silently repair numbers, doses, units, symbols, or tables. Open original documents for full instructions and warnings.
3. **Human personal accounts**: exact first-person contributions with explicit publication permission; not established emergency guidance. No AI impersonation or invented beliefs.
4. **Interface and editorial metadata**: AI assistance allowed when clearly separate from the substantive survival material.

## Intake requirements

Record publisher, title, direct source URL, final retrieval URL when redirected, retrieval time, publication/revision information when available, SHA-256, reuse basis and its evidence, and any transformation. A URL or a successful download alone does not prove accuracy or permission.

Original PDFs may contain links or refer to documents not yet included. Such dependencies must be recorded during library expansion; the starter library is not complete.

Store original diagrams and tables, not just extracted text. Preserve warnings and surrounding context. No synthetic fills for missing text or unavailable sources. Never label machine extraction a perfect transcript merely because a hash matches: a hash verifies byte identity, not substantive correctness.

## Maps

Map conversion is deterministic processing of publisher geography, not AI-generated geography. Preserve the downloaded original and conversion metadata. Show source, scale and limitations. No claim that a mapped road is passable or a facility is operating. Boundaries reflect publisher conventions and are not a political endorsement.

## Owner-acquired documents and online preparation

Public release media and the public Git repository may contain reviewed reusable sources, source metadata, and official publisher links. They must not contain restricted manuals merely because a publisher offers a free download.

An optional preparation workflow may help each owner acquire documents individually:

1. The owner deliberately opens online setup; normal startup must not contact publishers or require setup to use the bundled archive.
2. Source choices link to official publisher pages, including their download terms. A source link is not an installed document or a redistribution license.
3. Where a publisher requires download terms, consent, account access or payment, the owner uses the publisher's normal process. Gravestone must not bypass these steps, scrape gated material, or accept credentials on the publisher's behalf.
4. The owner may import an original PDF they are permitted to store and use. Preserve its bytes; keep owner-provided title/source metadata separate from publisher content. Imported text is a mechanical, unverified search aid, never an AI-written replacement.
5. Personal originals, metadata and extraction derivatives belong under the external configured data directory, not `content/`, Git, release artifacts, or a shared download cache. Label them Personal in the local library. User-entered provenance is not independently verified publisher provenance.
6. Downloads and imported maps/documents need explicit user action and honest storage/format/coverage reporting. Never silently retrieve a catalog or treat an internet connection as permission to download all sources.

This design separates software distribution from an owner's acquisitions. It does **not** establish that every download, extraction, backup, transfer or later use is lawful. Publisher terms, copyright, geography, licenses and access restrictions still apply. No DRM/access-control circumvention or permission to redistribute is supplied. A personal import does not confer a new license or make the source public domain.

Private acquisitions must be excluded from public builds and commits. Before sharing a populated USB, data directory or backup, the owner must review each source's permission requirements and remove restricted or private material as needed. The existing notebook/map backup is allowlisted and does not become a PDF backup just because PDFs are imported; new backup support needs its own explicit implementation and tests. Local files are not encrypted; anyone with filesystem access may read them.

An application restart with files intact is not proof of boot-media persistence, power-loss durability, or a populated USB's suitability for redistribution.

## Updates and conflicts

Record edition dates and review status. Do not silently merge conflicting guidance or treat old manuals as current. Retain superseded originals outside default results when an editorial update process is implemented. Medical and other consequential content needs qualified review.

## AI

No local model is included in the prototype. Later AI may assist document discovery; quoted source output must be controlled by retrieval software, not model promises. Unsupported questions must return a no-source result rather than generated advice. No interaction may impersonate a deceased contributor.

## Privacy

Personal notes and private first-person accounts remain outside the public repository and release images by default. Publishing a conversation excerpt requires an explicit decision, not an assumption that all shared material is redistributable.
