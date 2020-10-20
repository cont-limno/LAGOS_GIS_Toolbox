import arcpy
import nhd_plus_watersheds_tools as npwt

flowdir_raster = arcpy.GetParameterAsText(0)
catseed_raster = arcpy.GetParameterAsText(1)
nhdplus_gdb = arcpy.GetParameterAsText(2)
gridcode_table = arcpy.GetParameterAsText(3)
output_fc = arcpy.GetParameterAsText(4)

npwt.delineate_catchments(flowdir_raster, catseed_raster, nhdplus_gdb, gridcode_table, output_fc)