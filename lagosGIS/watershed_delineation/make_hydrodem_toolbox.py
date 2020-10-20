import arcpy
import nhd_plus_watersheds_tools as npwt

burned_raster = arcpy.GetParameterAsText(0)
filled_raster_output = arcpy.GetParameterAsText(1)

npwt.make_hydrodem(burned_raster, filled_raster_output)
