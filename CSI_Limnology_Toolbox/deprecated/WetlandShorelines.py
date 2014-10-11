# Filename: Wetland_Shorelines
# Purpose: Calculates the length in kilometers of each lake's shoreline that intersects wetlands.

import arcpy, os
from arcpy.sa import *

# User defined input parameters
nhd = arcpy.GetParameterAsText(0) # NHD 24k state geodatabase
nwi = arcpy.GetParameterAsText(1) # National wetlands inventory "CONUS_wet_poly" feature class for a state
lakes = arcpy.GetParameterAsText(2) # Lake polygons (can be nhdwaterbody or a subset derived from it)
topoutfolder = arcpy.GetParameterAsText(3) 

# Naming Convention
name = os.path.basename(nhd)
folder = os.path.splitext(name)[0]
if not os.path.exists(os.path.join(topoutfolder, folder)):
    os.mkdir(os.path.join(topoutfolder, folder))
outfolder = os.path.join(topoutfolder, folder)

# Environmental settings
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()
arcpy.env.outputCoordinateSystem = albers
arcpy.env.overwriteOutput = "TRUE"
mem = "in_memory"
arcpy.env.parallelProcessingFactor = "100%"

# Make an output gdb
arcpy.CreateFileGDB_management(outfolder, "scratch")
scratch = os.path.join(outfolder, "scratch.gdb")
arcpy.RefreshCatalog(outfolder)

# Filter expression for NHDWaterbody that eliminate most non-perrenial, non-lacustrine features by Fcode at a 1 & 10 ha min size. 
filter = '''"AreaSqKm" >=0.01 AND ( "FType" = 390 OR "FType" = 436) AND\
         ("FCode" = 39000 OR "FCode" = 39004 OR "FCode" = 39009 OR "FCode" = 39010 OR\
          "FCode" = 39011 OR "FCode" = 39012 OR "FCode" = 43600 OR "FCode" = 43613 OR\
          "FCode" = 43615 OR "FCode" = 43617 OR "FCode" = 43618 OR\
          "FCode" = 43619 OR "FCode" = 43621) OR ("Fcode" = 43601 AND "AreaSqKm" >= 0.1)'''

nwi_filter = """ "ATTRIBUTE" LIKE 'P%' """




# NHD feature class variables:
waterbody = lakes
network = os.path.join(nhd, "Hydrography", "HYDRO_NET")
junction = os.path.join(nhd, "Hydrography", "HYDRO_NET_Junctions")

# Make layer of NWI
arcpy.env.workspace = mem
arcpy.MakeFeatureLayer_management(nwi, os.path.join(mem, "nwi_lyr"))
nwi_lyr = os.path.join(mem, "nwi_lyr")

# Make a layer of filtered one hectare lakes
arcpy.MakeFeatureLayer_management(waterbody, os.path.join(mem, "oneha_lyr"), filter)
oneha_lyr = os.path.join(mem, "oneha_lyr")
arcpy.CopyFeatures_management(oneha_lyr, os.path.join(mem, "lakes"))
lakes = os.path.join(mem, "lakes")
                              

# Select wetlands intersecting lakes
arcpy.SelectLayerByLocation_management(nwi_lyr, "INTERSECT", oneha_lyr, "", "NEW_SELECTION")
arcpy.SelectLayerByAttribute_management(nwi_lyr, "SUBSET_SELECTION", nwi_filter)
arcpy.CopyFeatures_management(nwi_lyr, os.path.join(mem, "wet"))
wet = os.path.join(mem, "wet")

# Add a hectares field to wetlands
arcpy.AddField_management(wet, "WETLAND_HA", "DOUBLE")
arcpy.CalculateField_management(wet, "WETLAND_HA", "!shape.area@hectares!", "PYTHON")


# Get length of lake shore traversing bordering wetlands

arcpy.PolygonToLine_management(lakes, os.path.join(mem, "shorelines"))
shorelines = os.path.join(mem, "shorelines")
infcs = [shorelines, wet]
intersection = arcpy.Intersect_analysis(infcs, os.path.join(mem, "shoreint"))
shoreint = os.path.join(mem, "shoreint")
arcpy.AddField_management(shoreint, "WetShoreKm", "DOUBLE")
arcpy.CalculateField_management(shoreint, "WetShoreKm", "!shape.length@kilometers!", "PYTHON")

fieldmappings = arcpy.FieldMappings()
fieldmapID = arcpy.FieldMap()
fieldmapKM = arcpy.FieldMap()
fieldmapID.addInputField(lakes, "Permanent_Identifier")
fieldmapKM.addInputField(shoreint, "WetShoreKm")
fieldmapKM.mergeRule = 'SUM'
fieldmappings.addFieldMap(fieldmapID)
fieldmappings.addFieldMap(fieldmapKM)

arcpy.SpatialJoin_analysis(lakes, shoreint, os.path.join(outfolder, "WetlandConnect.shp"),'','',fieldmappings)
output = os.path.join(outfolder, "WetlandConnect.shp")
arcpy.AddField_management(output,"WetlandCNT", "LONG")
arcpy.CalculateField_management(output, "WetlandCNT","!Join_Count!", "PYTHON")
arcpy.DeleteField_management(output, "Join_Count")





