# filename: add_lake_seeds_toolbox.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import arcpy
import nhd_plus_watersheds_tools as npwt

nhdplus_catseed_raster = arcpy.GetParameterAsText(0)
nhdplus_gdb = arcpy.GetParameterAsText(1)
gridcode_table = arcpy.GetParameterAsText(2)
eligible_lakes_fc = arcpy.GetParameterAsText(3)
output_raster = arcpy.GetParameterAsText(4)

npwt.add_lake_seeds(nhdplus_catseed_raster, nhdplus_gdb, gridcode_table, eligible_lakes_fc, output_raster)