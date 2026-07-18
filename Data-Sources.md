# Real-Data Acquisition, Ingestion, and Validity Domains

The pipeline consumes five canonical 1-degree lunar science grids, a terrain-validity mask
derived from the external USGS geology product, and an analyst-declared basin catalogue. The
native institutional products are retained unchanged under
`data/raw/sources/`; derived analysis inputs live in `data/raw/`. Byte provenance and raster
schema checks establish file identity and computational reproducibility. They do **not**
establish that a retrieval is scientifically valid in every terrain where it has a numeric
value.

```text
data/raw/sources/                 immutable downloads, extracted archives, source manifest
data/raw/*.tif                    canonical lunar-geographic analysis grids
data/raw/tio2_mare_validity.tif   USGS-derived mare-domain sensitivity mask
data/raw/basins.csv               six predeclared major basin centers and radii
data/raw/antipodes.csv            antipodes derived from those centers
data/raw/real_data_manifest.json  conversions and output SHA-256 hashes
```

## Reproducible workflow

```bash
python -m src.acquire all
python -m src.ingest all
python -m src.ingest validate
python main.py --data-mode real --mode full
```

Acquisition families can also be verified or downloaded independently:

```bash
python -m src.acquire lroc
python -m src.acquire grail usgs jaxa
```

Existing files are reused only after they match code-pinned SHA-256 values. `--force`
redownloads a family, verifies the temporary payload, and only then replaces a known-good
file. Downloads use `.part` files, resume when the server supports ranges, and retry. ZIP
extraction rejects absolute paths, traversal, symlinks, missing members, and injected
members; every extracted byte is checked directly against its pinned archive.

`src.ingest all` is intentionally all-or-nothing. It verifies every source byte against
`source_manifest.json`, converts into a temporary staging directory, validates the entire
schema, creates `real_data_manifest.json`, validates provenance, and then promotes the
outputs. It never substitutes generated data or silently skips an unavailable source.

## Exact products and conversions

| Layer | Pinned native product | Conversion to canonical grid | Canonical output |
|---|---|---|---|
| Magnetic target | JAXA DARTS `SLN-L-LMAG-5-MA-GRID-OPTION-V1.0`, `MA_GDOP_001` | absolute total-field `F`; periodic linear interpolation of 64,440 points | `magnetic_anomaly.tif`, nT |
| TiO2 (candidate spatial proxy) | LROC WAC TiO2, `LRO-L-LROC-5-RDR-V1.0/LROLRC_2001`, eight IMG/PDS4-label pairs | decode native payloads; normalize longitude seam; mask values outside 0–15 wt.%; area-average | `tio2_abundance.tif`, wt.% |
| Bouguer gravity | GRAIL GRGM1200A Bouguer disturbance, degree/order 180 GeoTIFF | normalize longitude seam; area-average | `bouguer_gravity.tif`, mGal |
| Crustal thickness | GRAIL Crustal Thickness Archive v1, `Model1_thick.dat` | parse 0.25-degree grid; drop duplicate 360-degree seam; area-average | `crustal_thickness.tif`, km |
| Geologic age | USGS Unified Geologic Map of the Moon 1:5M GIS v2, `GeoUnits.shp` | rasterize `FIRST_Un_1`; Imbrian=2, Nectarian and ambiguous Imbrian-Nectarian=1, all others=0 | `geologic_age.tif` |
| TiO2 terrain validity | same external USGS GIS v2 `GeoUnits.shp` | rasterize exact case-sensitive `FIRST_Unit` symbols `Em`, `Im1`, `Im2`, `Imd` as 1; all other mapped units as 0; nearest-neighbor reprojection | `tio2_mare_validity.tif`, boolean/0–1 |
| H2 benchmark geometry | six approximate centers/radii declared in `src/basins.py` | `antipode = (wrap(lon + 180), -lat)` | `basins.csv`, `antipodes.csv` |

The chosen crustal-thickness model is the archive's published Model 1: 12% porosity,
34 km global mean, and 3,220 kg/m3 mantle density. GRAIL gravity and thickness are in a
Moon Principal-Axes frame; their subpixel PA/ME offset at the 1-degree analysis scale is
recorded in the manifest as a control-layer uncertainty, not silently treated as exact.

## Sources and citations

- LROC WAC TiO2: NASA PDS/ASU volume `LROLRC_2001`; PDS3 dataset DOI
  `10.17189/1520341`, PDS4 bundle DOI `10.17189/a6a1-mw73`; Sato et al. (2017),
  *Icarus* 296, DOI `10.1016/j.icarus.2017.06.013`. Native coverage is 70 S to 70 N.
- GRAIL Bouguer: NASA PDS Geosciences GRGM1200A L=180; Lemoine et al. (2014), DOI
  `10.1002/2014GL060027`, and Goossens et al. (2016), LPSC abstract 1484.
- GRAIL thickness: archive DOI `10.5281/zenodo.997347`; Wieczorek et al. (2013),
  *Science* 339, DOI `10.1126/science.1231530`.
- USGS geology: Fortezzo, Spudis, and Harrel (2020), Unified Geologic Map of the Moon,
  GIS v2 dated 2020-03-03, 1:5M.
- JAXA LMAG: Tsunakawa et al. (2015), DOI `10.1002/2014JE004785`.

Resolved URLs, versions, byte sizes, MD5 values, code-pinned SHA-256 values, licenses,
and per-member extraction hashes are machine-readable in
`data/raw/sources/source_manifest.json` (schema version 2).

## Canonical schema and rejection checks

All rasters must be one-band float32 GeoTIFFs with `nodata=-9999`, exact global bounds,
an aligned `from_origin(-180, 90, res, res)` transform, and lunar-geographic CRS with
radius 1,737,400 m. Resolution must divide both 180 and 360 exactly.

Validation rejects:

- missing, unreadable, misaligned, multi-band, wrong-dtype, or Earth-CRS grids;
- insufficient per-layer or common valid coverage;
- nonfinite/out-of-range physical values and invalid/missing age classes;
- malformed, duplicate, or out-of-range basin coordinates/radii;
- antipodes that do not exactly match the mathematical transform;
- missing, stale, or hash-mismatched source/canonical manifests.

LROC TiO2 is intentionally nodata poleward of 70 degrees, so its expected canonical numeric
coverage is 77.78%. The five-layer common footprint is checked accordingly. That coverage
check is **not** a mare/highlands validity check: a finite value can still be out-of-domain
for the scientific use proposed here.

The terrain mask fails closed if the external USGS unit field is absent or ambiguous and
never substitutes TiO2, magnetic outcome, age class, or location for terrain validity. The
processed modeling table exposes it as `tio2_terrain_valid`. The default terrain sensitivity
assigns spatial folds on the full analysis scope before filtering, compares full and mare
scopes with the same inherited folds, and uses row-local `tio2` plus controls. Buffered TiO2
features are excluded from that default comparison because a center-pixel mask alone does not
prove that every contributing buffer pixel lies in the supported terrain domain.

Schema-only validation without real provenance exists solely for test fixtures:

```bash
python -m src.ingest validate --allow-missing-provenance
```

Do not use that flag for a scientific run. `main.py --data-mode real` always requires
verified provenance.

## Scientific cautions

- One degree is about 30 km at the equator — a horizontal ground resolution, not a
  measurement height — and is close to the useful resolution floor of the surface
  magnetic map (Kaguya/Lunar Prospector SVM). Finer interpolation does not create
  independent evidence.
- The Bouguer field is ingested in full. The exploratory difference-of-Gaussians
  band-pass is applied later in preprocessing.
- Surface TiO2 is an indirect optical-regolith proxy, not a measurement of the older/deeper
  material that necessarily carries the magnetic remanence. Present-day spatial mismatch
  cannot be interpreted as a timing test of a dynamo.
- The cited LROC WAC algorithm and Sato et al. product concern **mare** TiO2. The current
  ingestion masks polar absence and implausible numeric values but does not exclude highlands.
  Quantitative highland values are therefore out-of-domain for this analysis unless
  independently validated; they must not be read as reliable low-Ti measurements.
- The implemented mare-domain sensitivity uses the external USGS Unified Geologic Map GIS v2
  and a frozen allowlist: `Em`, `Im1`, `Im2`, and `Imd` (Eratosthenian mare, lower/upper
  Imbrian mare, and mare dome). It is still an approximate 1:5M mapped-geology proxy: mapped
  superposed units are excluded, and boundary rasterization depends on source generalization
  and analysis resolution. In the legacy Imbrian scope it retains 6,232 pixels, 58 positives,
  and nine nominal blocks. Raw TiO2+controls PR-AUC is 0.1252 versus 0.0576 for controls;
  fold increments [0.2615, 0.0834, -0.0018, -0.0070, 0.0020] yield one-sided paired
  Wilcoxon *p* = 0.21875. The post-hoc result is positive in the mean but not statistically
  significant, unstable, and inconclusive.
- The six-basin catalogue is a declared approximate model choice, not an observational
  download or exhaustive impact database. Its analytically exact antipodes are exact only
  relative to those approximate inputs. H2 is therefore a benchmark, not assured truth.
- The 5 nT binary target discards continuous field magnitude and yields about 286 clustered
  positives in the primary cell. Numeric pixel count must not be mistaken for independent
  sample size; the bundled diagnostics estimate `n_eff ≈ 1`.
