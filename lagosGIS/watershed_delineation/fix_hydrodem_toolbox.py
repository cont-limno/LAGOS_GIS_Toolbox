# filename: fix_hydrodem_toolbox.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import arcpy
import nhd_plus_watersheds_tools as npwt

hydrodem_raster = arcpy.GetParameterAsText(0)
lagos_catseed_raster = arcpy.GetParameterAsText(1)
out_raster = arcpy.GetParameterAsText(2)

npwt.revise_hydrodem(hydrodem_raster, lagos_catseed_raster, out_raster)