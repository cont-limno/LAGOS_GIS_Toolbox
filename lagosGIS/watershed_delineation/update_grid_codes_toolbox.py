import arcpy
import nhd_plus_watersheds_tools as npwt

nhdplus_gdb = arcpy.GetParameterAsText(0)
output_table = arcpy.GetParameterAsText(1)

npwt.update_grid_codes(nhdplus_gdb, output_table)