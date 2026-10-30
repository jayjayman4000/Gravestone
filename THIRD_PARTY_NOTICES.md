# Third-party notices

The MIT software license does **not** apply to third-party documents, data, trademarks, Debian packages, or personal accounts.

## FEMA

Source: Federal Emergency Management Agency (FEMA), *Are You Ready? An In-Depth Guide to Citizen Preparedness*.

Original: https://www.ready.gov/sites/default/files/2021-11/are-you-ready-guide.pdf

Retained unchanged as a U.S. federal government publication. This does not assert ownership of government marks or third-party material, or imply federal endorsement. Source and rights metadata are in `content/manifest.json`; general federal copyright guidance is archived in `content/rights/`. Reuse outside the United States and any future third-party assets need separate review.

## CDC

Source: Centers for Disease Control and Prevention (CDC), *Make Water Safe During an Emergency (Print-only)*.

Original: https://www.cdc.gov/water-emergency/media/pdfs/make-water-safe-during-emergency-p.pdf

The material is otherwise available on the CDC website for no charge. The original PDF is retained without changes to substantive content. Attribution: **Source: CDC**.

Gravestone's use of these materials and links does not imply endorsement by CDC, ATSDR, HHS, or the United States Government of Gravestone, its contributors, products, facilities, or services. Reference to specific commercial products, manufacturers, companies, or trademarks does not constitute endorsement or recommendation by the U.S. Government, Department of Health and Human Services, or Centers for Disease Control and Prevention.

Agency reuse terms: https://www.cdc.gov/other/agencymaterials.html (snapshot archived under `content/rights/`). Government logos contained in original documents are not used as Gravestone branding. Copyright law and trademark restrictions remain applicable.

## Natural Earth

Made with Natural Earth. Publisher: Natural Earth / NACIS. Public-domain geographic data.

Original dataset: https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip

Terms: https://www.naturalearthdata.com/about/terms-of-use/ (snapshot archived).

Original ZIP retained. The app's GeoJSON is a deterministic conversion of the 1:110 million country-boundary shapefile, with reduced attribute fields; no generated coordinates or borders. Not suitable for street navigation. Includes small-scale omissions and publisher boundary conventions.

## Search derivatives

Extracted with pypdf 6.21.4 and fonttools 4.68.0; GeoJSON converted using pyshp 3.1.6. These are ingestion tools, not bundled app runtime dependencies. Extracted text is an unverified search aid and may have encoding, reading-order, numeric or table errors. It is not a replacement for original PDFs.

## Local keyword-assistance model and runtime

The 0.2.0 image build includes Qwen's official `Qwen3-0.6B-Q8_0.gguf` model under Apache-2.0 and a source-built llama.cpp `b12001` runtime under MIT. Their original license texts, the upstream model card, immutable revisions, download URLs, byte sizes and SHA-256 pins are retained under `ai/`; see `ai/package.json` and `ai/README.md`. The image also carries the complete pinned llama.cpp source archive and runtime build provenance, including bundled third-party notices. Model weights/binaries are installed during image construction, not committed to the repository.

The model only proposes search keywords; publisher originals remain authoritative. Neither Qwen nor llama.cpp authors are represented as endorsing Gravestone or its emergency suitability. Their licenses do not relicense publisher documents or Debian packages.

## Debian live system

Linux, Debian packages, browser and bootloader retain their own licenses. Package licenses reside under `/usr/share/doc/*/copyright` in the live system. The build should retain package inventories and source-retrieval instructions; corresponding-source obligations must be reviewed before wider redistribution. No hardware warranty, emergency fitness guarantee, or agency endorsement is claimed.
