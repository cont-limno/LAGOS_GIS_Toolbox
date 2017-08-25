LAGOS GIS Toolbox
===================

This is an ArcGIS toolbox for landscape limnology created from a collection of Python script tools. It was used to create the [LAGOS-NE database](https://lagoslakes.org/) and is currently being updated in 2017 and 2018 for the creation of the LAGOS-US database.

This toolbox was created with ArcGIS 10.1. It is being maintained in ArcGIS 10.3. It may work for other versions of ArcGIS.

## Releases & Citation
Release [v1.0](https://github.com/cont-limno/LAGOS_GIS_Toolbox/tree/v1.0) corresponds to the methods documented in the following manuscript:

Soranno, P. A., Bissell, E. G., Cheruvelil, K. S., Christel, S. T., Collins, S. M., Fergus, C. E., ... & Scott, C. E. (2015). Building a multi-scaled geospatial temporal ecology database from disparate data sources: fostering open science and data reuse. *GigaScience, 4*(1), 28.

## Requires
* Spatial Analyst extension (some tools)
* [RivEX software](http://www.rivex.co.uk/) (proprietary) to create the input (rivers with Strahler order assignment) to the Lake Order Tool.
* While some steps in our workflow at Michigan State University are conducted in a supercomputing environment (ie Taudem
pitremove & d8flowdir were ported to RHEL to get the data processed faster), you can do these steps on a workstation
easily enough with ESRI tools or with the [Taudem](http://hydrology.usu.edu/taudem/taudem5/index.html) tool suite.
## Installation

![](installation.png)

* Open the ArcToolbox Pane

* Right click to access the Add Toolbox command

* Navigate to `LAGOS_GIS_Toolbox.tbx`

* (Optional) Right click on ArcToolbox root, then click "Save Settings > To Default" to save this toolbox to your default tools

## Tools
**Lake Analysis**
* Lake Connectivity Classification
* Lake Order Classification
* Lake-Wetland Connections
* Upstream Lakes

**Summarize Data by Zones**
* Lakes in Zones
* Line Density
* Point Density
* Polygons in Zones
* Streams in Zones
* Subset Overlapping Zones
* Wetlands in Zones
* Zonal Attribution of Raster Data

**Utilities**
* Add Unique Fields
* Drop Fields and Calc Geometry
* Export to CSV
* Merge Many Feature Classes
* Merge Many Shapefiles
* Merge NHD Features
* Merge NHD Features without Deduplication
* Mosaic to Subregion
* Prefix Field Names

**Watershed Delineation**
1. State and Mosaic Data for Subregion
2. Burn Flowlines into DEM
3. Clip DEM to HU8 Boundaries
4. (Step 4 (Fill Pits) is not in toolbox)
5. Create HU8 Walls
6. (Step 6 (Flow Direction) is not in toolbox)
7. Convert TauDEM Flow Direction Raster to ArcGIS Format
8. Create Pour Points
9. Create Lake Watersheds

**Wetland Analysis**
1. Preprocess NWI
2. Wetland Order

---

The toolbox is not formally supported. You can direct questions to the current maintainer, Nicole Smith (smithn78@msu.edu), or the project PI, Patricia Soranno (soranno@msu.edu).

