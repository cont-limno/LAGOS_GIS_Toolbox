# filename: make_hydrodem_toolbox.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import arcpy
import nhd_plus_watersheds_tools as npwt

burned_raster = arcpy.GetParameterAsText(0)
filled_raster_output = arcpy.GetParameterAsText(1)

npwt.make_hydrodem(burned_raster, filled_raster_output)
