import arcpy
import nhd_plus_watersheds_tools as npwt

hydrodem_raster = arcpy.GetParameterAsText(0)
lagos_catseed_raster = arcpy.GetParameterAsText(1)
out_raster = arcpy.GetParameterAsText(2)

npwt.fix_hydrodem(hydrodem_raster, lagos_catseed_raster, out_raster)