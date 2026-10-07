# Copernicus data in this folder

Two files here are clips of Copernicus data. **They are not covered by the
repository's AGPL-3.0 licence**: each is distributed under its own licence,
below, and anyone who redistributes them is bound by the same terms.
`fetch_copernicus.py` rebuilds both from the public archives.

## `monte_baldo_dem.tif` — Copernicus DEM GLO-30

A 252 x 180 window of tile N45 E010, unchanged apart from the crop, read from
the AWS Open Data copy (`copernicus-dem-30m`).

Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence
and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and
ESA; all rights reserved.

The organisations in charge of the Copernicus programme by law or by delegation
do not incur any liability for any use of the Copernicus WorldDEM-30.

Licence: *Licence for Copernicus DEM instance COP-DEM-GLO-30-F Global 30m Full,
Free & Open*, shipped with every tile as
[`INFO/eula_F.pdf`](https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E010_00_DEM/INFO/eula_F.pdf).
Collection DOI: [10.5270/ESA-c5d3d65](https://doi.org/10.5270/ESA-c5d3d65).
Nothing here implies endorsement by the providers or licensors.

## `monte_baldo_s2.tif` — Sentinel-2 L2A

Bands B04 and B08 of item `S2C_32TPR_20250813_0_L2A` (13 August 2025), cropped
and stacked into one file with a declared scale, read from the AWS Open Data
copy (`sentinel-cogs`, indexed by Element 84 Earth Search).

Contains modified Copernicus Sentinel data 2025.

Licence: [Legal notice on the use of Copernicus Sentinel Data and Service
Information](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice).
