# filename: fix_hydrodem_toolbox.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import arcpy
import nhd_plus_watersheds_tools as npwt

nhd_gdb = arcpy.GetParameterAsText(0)
hydrodem_raster = arcpy.GetParameterAsText(1)
filldepth_raster = arcpy.GetParameterAsText(2)
lagos_catseed_raster = arcpy.GetParameterAsText(3)
out_raster = arcpy.GetParameterAsText(4)

npwt.revise_hydrodem(nhd_gdb, hydrodem_raster, filldepth_raster, lagos_catseed_raster, out_raster)