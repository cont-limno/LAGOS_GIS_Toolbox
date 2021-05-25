# filename: delineate_catchments_toolbox.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import arcpy
import nhd_plus_watersheds_tools as npwt

flowdir_raster = arcpy.GetParameterAsText(0)
catseed_raster = arcpy.GetParameterAsText(1)
nhdplus_gdb = arcpy.GetParameterAsText(2)
gridcode_table = arcpy.GetParameterAsText(3)
output_fc = arcpy.GetParameterAsText(4)

npwt.delineate_catchments(flowdir_raster, catseed_raster, nhdplus_gdb, gridcode_table, output_fc)