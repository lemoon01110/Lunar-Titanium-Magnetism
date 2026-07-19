# References

All sources this project relies on. DOIs are the authoritative identifiers; where a
product is an abstract or an archive, that is stated explicitly. Dataset versions,
access details, and byte-level provenance are in [Data-Sources.md](Data-Sources.md);
machine-readable citation metadata is in [CITATION.cff](CITATION.cff).

## How to cite this repository

Use the **"Cite this repository"** button on GitHub (generated from `CITATION.cff`), or:

> Jack Wu (lemoon01110). *Surface TiO2 and Lunar Crustal Magnetism: An Underpowered
> Spatial Co-location Analysis* (v2.0.0), 2026.
> https://github.com/lemoon01110/Lunar-Titanium-Magnetism
> ORCID: https://orcid.org/0009-0004-1710-9018

**Version note:** **v2.0.0** is the current release (surface-evaluated Tsunakawa/Wieczorek
magnetic target, 10/25 nT thresholds, TiO₂ quantitative mask). **v1.0.0 is superseded** and
must **not** be cited or deposited to Zenodo — it used JAXA `MA_GDOP_001` (a 30 km altitude
grid wrongly treated as a surface map) with 5/10 nT thresholds. An earlier reading of the
altitude-product run used the machine label `NOT_SUPPORTED`; the dated amendments in
`Pre-Registration.md` explain why the power-calibrated interpretation is
`INCONCLUSIVE_LOW_POWER`. The repository's scientific scope is the surface-map co-location
question above; it is not a temporal test of dynamo operation.

The analysis plan is an **author-declared prospective plan** whose timing cannot be
independently verified (all git history begins after results already existed).

## Scientific literature

**Scientific motivation, diagnostic benchmark, and hypothesis-space context.**

1. **Nichols, C. I. O., Wade, J. & Stephenson, S. N.** (2026). An intermittent dynamo
   linked to high-titanium volcanism on the Moon. *Nature Geoscience* 19, 425–431.
   https://doi.org/10.1038/s41561-026-01929-y — physical motivation for the candidate
   TiO2 proxy. Favored mechanism: radiogenic melting of ilmenite-bearing cumulates at the
   core–mantle boundary after overturn, increasing core heat flux — not simply continued
   sinking of Ti-rich material. This repository does **not** directly test that
   temporal/thermal mechanism; it tests a new present-day spatial operationalization.
2. **Hood, L. L. & Artemieva, N. A.** (2008). Antipodal effects of lunar basin-forming
   impacts: Initial 3D simulations and comparisons with observations. *Icarus* 193(2),
   485–502. https://doi.org/10.1016/j.icarus.2007.08.023 — motivates the H2
   distance-to-nearest-antipode benchmark. The repository's six-basin geometry is an
   approximate analyst encoding, not an exact representation of this literature.
3. **Lin, R. P., Anderson, K. A. & Hood, L. L.** (1988). Lunar surface magnetic field
   concentrations antipodal to young large impact basins. *Icarus* 74(3), 529–541.
   https://doi.org/10.1016/0019-1035(88)90119-4 — empirical motivation for treating
   impact-antipode association as a serious diagnostic benchmark.
4. **Hood, L. L., Zakharian, A., Halekas, J., Mitchell, D. L., Lin, R. P., Acuña, M. H. &
   Binder, A. B.** (2001). Initial mapping and interpretation of lunar crustal magnetic
   anomalies using Lunar Prospector magnetometer data. *J. Geophys. Res. Planets* 106(E11),
   27,825–27,839. https://doi.org/10.1029/2000JE001366 — maps extensive Imbrium- and
   Crisium-antipodal anomaly groups while discussing the geological ambiguity of their origin.
5. **Narrett, I. S., Oran, R., Chen, Y., Miljković, K., Tóth, G., Mansbach, E. N. &
   Weiss, B. P.** (2025). Impact plasma amplification of the ancient lunar dynamo.
   *Science Advances* 11, eadr7401. https://doi.org/10.1126/sciadv.adr7401 — part of the
   broader hypothesis space (see [Fallacy-Audit.md](Fallacy-Audit.md), F5); this study
   does not adjudicate it.

## Data products

**Target — surface crustal magnetic field (v2.0.0).** Tsunakawa et al. (2015) surface-vector
mapping (SVM) model, evaluated at lunar mean radius via the Wieczorek T2015_449
spherical-harmonic expansion (Zenodo https://doi.org/10.5281/zenodo.3873648). Horizontal
grid resolution remains 1° (~30 km). **Superseded v1 product:** JAXA DARTS
`MA_GDOP_001` is a **30 km altitude** grid and must never be described as a surface map.
Reference: **Tsunakawa, H., Takahashi, F., Shimizu, H., Shibuya, H. & Matsushima, M.**
(2015). Surface vector mapping of magnetic anomalies over the Moon using Kaguya and Lunar
Prospector observations. *J. Geophys. Res. Planets* 120, 1160–1185.
https://doi.org/10.1002/2014JE004785

**Feature — surface TiO2 abundance.** LROC WAC TiO2 map, NASA PDS / ASU volume
`LRO-L-LROC-5-RDR-V1.0` (`LROLRC_2001`). Dataset DOIs: PDS3
https://doi.org/10.17189/1520341, PDS4 https://doi.org/10.17189/a6a1-mw73.
Reference: **Sato, H., Robinson, M. S., Lawrence, S. J., et al.** (2017). Lunar mare TiO2
abundances estimated from UV/Vis reflectance. *Icarus* 296, 216–238.
https://doi.org/10.1016/j.icarus.2017.06.013

The product sets values **&lt;2 wt% to 1 wt%** (non-quantitative). Primary analysis requires
`tio2_quantitative` (≥2 wt%); ~88.7% of jointly valid cells are below detection. The word
**mare** in the product reference is methodologically important. The primary numeric
footprint is not a terrain-validity mask, so its highland values remain out-of-domain. A
separate post-hoc sensitivity uses the cited USGS mapped units as an approximate mare proxy;
it excludes mapped highlands but does not establish the formal pixel-level WAC validity domain.

**Feature — Bouguer gravity.** GRAIL GRGM1200A Bouguer field (degree/order 180 product),
NASA PGDA / PDS Geosciences.
Model reference: **Goossens, S., et al.** (2016). A global degree and order 1200 model of
the lunar gravity field using GRAIL mission data. *47th LPSC*, Abstract #1484. GRAIL
gravity-modelling lineage: **Lemoine, F. G., et al.** (2014), GRGM900C, *Geophys. Res.
Lett.* 41. https://doi.org/10.1002/2014GL060027

**Control — crustal thickness.** GRAIL Crustal Thickness Archive (Model 1: 12% porosity,
34 km mean, 3220 kg/m³ mantle). Archive DOI https://doi.org/10.5281/zenodo.997347.
Reference: **Wieczorek, M. A., et al.** (2013). The crust of the Moon as seen by GRAIL.
*Science* 339, 671–675. https://doi.org/10.1126/science.1231530

**Chronology — geologic age.** USGS Unified Geologic Map of the Moon, GIS v2, 1:5,000,000
scale (`GeoUnits.shp`, `FIRST_Un_1`).
Reference: **Fortezzo, C. M., Spudis, P. D. & Harrel, S. L. (Shannon L. Harrel)** (2020).
Release of the Digital Unified Global Geologic Map of the Moon at 1:5,000,000-Scale.
*51st LPSC*, Abstract #2760.

**H2 benchmark geometry — basin catalogue.** Six approximate major-basin centres/radii
declared in [`src/basins.py`](src/basins.py); antipodes derived as
`(wrap(lon+180), -lat)`. This is a disclosed analysis choice, not a downloaded product or
an authoritative exhaustive catalogue (see [Data-Sources.md](Data-Sources.md)).

## Terrain-validity mask source

The post-hoc mare-domain sensitivity derives its mask from the already cited **USGS Unified
Geologic Map of the Moon GIS v2** rather than from TiO2 or magnetic outcomes. Its exact
allowlist and reporting limits are in [Data-Sources.md](Data-Sources.md).
