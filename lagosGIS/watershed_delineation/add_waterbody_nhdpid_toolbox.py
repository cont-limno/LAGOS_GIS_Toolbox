import arcpy
import nhd_plus_watersheds_tools as npwt

nhdplus_waterbody_fc = arcpy.GetParameterAsText(0)
eligible_lakes_fc = arcpy.GetParameterAsText(1)

npwt.add_waterbody_nhdpid(nhdplus_waterbody_fc, eligible_lakes_fc)