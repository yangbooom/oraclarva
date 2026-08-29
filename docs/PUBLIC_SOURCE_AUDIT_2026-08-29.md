# Public source audit — 2026-08-29 UTC

This audit applies the source gates in `data/sources/source_manifest_v0.yaml`. It does not promote an image, paper, or repository into measured L1 geometry merely because it is public.

## CIL:41824

The official record identifies a 2750 × 2341 confocal projection, red muscle attachment-site labels, and green sensory dendrites. It offers a 3.15 MB OME-TIFF and 589.73 KB submitted file, but the record reports no instar, pixel size, Z dimension, or commercial-derivative permission. Its license is CC BY-NC-ND.

Decision: reference only. Do not derive coordinates, redistribute in the app, or call it L1. The host's current TLS certificate chain could not be verified in this environment, so no artifact or checksum was recorded; TLS verification was not bypassed.

Source: https://www.cellimagelibrary.org/images/41824 and https://doi.org/10.7295/W9CIL41824

## Mendeley c9fdgs69xx.3

The public API confirms version 3 (2026-08-14), CC BY 4.0. Longitudinal L1 recordings are under `Figure 5/Figure 5 A-B`, not Figure 1. The tree contains five control animals and five `CQ U Is - RPR` animals, each with L1 and L3 children. The ten L1 folders contain 40 AVI files (about 0.27–6.01 MB each) with per-file SHA-256 and public download URLs.

Decision: no bulk download and no repository bundling. These are longitudinal MN1/NMJ injury-plasticity recordings rather than muscle attachment or CSA data. The public API exposed no separate analysis result inside the L1 folders. File-level scale metadata must be verified before any image-coordinate use.

Metadata: https://data.mendeley.com/public-api/datasets/c9fdgs69xx/folders/3

Files: `https://data.mendeley.com/public-api/datasets/c9fdgs69xx/files?folder_id=<folder UUID>&version=3`

Dataset: https://doi.org/10.17632/c9fdgs69xx.3

## BossDB `1st instar` candidate

The matching project is `gerhard2017` (DOI `10.60533/BOSS-2017-0DCV`). Its declared anatomy is `Drosophila-LarvaVentralNerveCord`; it compares nociceptive circuits across L1 and L3. The current public BossDB metadata exposes collection `gerhard2017`, experiment `drosophila_melanogaster_third_instar_larva`, channel `em`, dimensions 61952 × 46592 × 2156, and 2.3 × 2.3 × 50 nm voxels.

Decision: this is not the Peale complete first-instar whole-body volume. It is excluded from body-wall/cuticle/muscle geometry work and remains reference-only. No publicly exposed L1 experiment was present in the 2026-08-29 metadata snapshot.

Project: https://bossdb.org/project/gerhard2017

Public resource API: https://api.bossdb.io/v1/mgmt/resources/gerhard2017

## Dryad cold nociception

The exact dataset is `10.5061/dryad.h44j0zpxv`, published 2026-06-18. `muscle_figure.xlsx` contains segmental and individual-muscle calcium responses; its README explicitly identifies the animals as third instar.

Decision: L3-labeled relative activation prior only. Never use it for L1 absolute length, CSA, or Fmax, and do not treat cold contraction recruitment as ordinary crawling recruitment.

Dataset: https://doi.org/10.5061/dryad.h44j0zpxv

## Remaining blocker

No verified, publicly downloadable Peale whole-body L1 EM volume was found in BossDB. CIL:41824 cannot legally or metrically support a commercial derived attachment atlas. Therefore coordinate extraction and image-to-model reprojection tests remain blocked on a suitable licensed, scaled source; the manifest deliberately fails closed rather than fabricating a fixture with biological meaning.
