import arcpy
import nhd_plus_watersheds_tools as npwt

hydrodem_raster = arcpy.GetParameterAsText(0)
flow_direction_raster_out = arcpy.GetParameterAsText(1)

npwt.flow_direction(hydrodem_raster, flow_direction_raster_out)