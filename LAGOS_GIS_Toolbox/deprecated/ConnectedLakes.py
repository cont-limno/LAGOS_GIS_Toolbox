# ConnectedLakes.py

import arcpy, os

nwi_input = arcpy.GetParameterAsText(0)
nhd = arcpy.GetParameterAsText(1)
outfc = arcpy.GetParameterAsText(2)
mem = "in_memory"
arcpy.env.workspace = mem
cs = arcpy.SpatialReference()
cs.factoryCode = 102039
cs.create()
arcpy.env.outputCoordinateSystem = cs
where = """"ATTRIBUTE" LIKE 'P%' AND "WETLAND_TY" <> 'Freshwater Pond'"""
arcpy.MakeFeatureLayer_management(nwi_input, "nwi", where)
arcpy.env.overwriteOutput = True
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.extent = "nwi"
fms = arcpy.FieldMappings()
fms.addTable("nwi")
arcpy.SpatialJoin_analysis("nwi", nhd, outfc, '', '', fms, '', "30 meters")