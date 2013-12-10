# ConnectedWetlands.py

import arcpy, os
from arcpy.sa import *

# User defined input parameters
nhd = arcpy.GetParameterAsText(0) # NHD 24k state geodatabase
nwi = arcpy.GetParameterAsText(1) # National wetlands inventory "CONUS_wet_poly" feature class for a state
#ws = arcpy.GetParameterAsText(2) # Watersheds - usually the output from cumulative watersheds tool.
outfolder = arcpy.GetParameterAsText(2) 

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


# NHD feature class variables:
flowline = os.path.join(nhd, "Hydrography", "NHDFlowline")
waterbody = os.path.join(nhd, "Hydrography", "NHDWaterbody")
network = os.path.join(nhd, "Hydrography", "HYDRO_NET")
junction = os.path.join(nhd, "Hydrography", "HYDRO_NET_Junctions")

# Make layer of NWI
arcpy.env.workspace = mem
arcpy.MakeFeatureLayer_management(nwi, os.path.join(mem, "nwi_lyr"))
nwi_lyr = os.path.join(mem, "nwi_lyr")

# Make a layer of filtered one hectare lakes
arcpy.MakeFeatureLayer_management(waterbody, os.path.join(mem, "oneha_lyr"), filter)
oneha_lyr = os.path.join(mem, "oneha_lyr")

# Select wetlands intersecting lakes
arcpy.SelectLayerByLocation_management(nwi_lyr, "INTERSECT", oneha_lyr, "", "NEW_SELECTION")
arcpy.CopyFeatures_management(nwi_lyr, os.path.join(mem, "wet"))
wet = os.path.join(mem, "wet")

# Add a hectares field to wetlands
arcpy.AddField_management(wet, "WETLAND_HA", "DOUBLE")
arcpy.CalculateField_management(wet, "WETLAND_HA", "!shape.area@hectares!", "PYTHON")

# Filter expressions for NWI wetland types
forested_exp = """ "WETLAND_TY" = 'Freshwater Forested/Shrub Wetland' """
emergent_exp = """ "WETLAND_TY" = 'Freshwater Emergent Wetland' """
other_exp = """ "WETLAND_TY" = 'Other' """

# Make 3 wetland feature classes 
arcpy.MakeFeatureLayer_management(wet, os.path.join(outfolder, "wet.lyr"))
wet_lyr = os.path.join(outfolder, "wet.lyr")

arcpy.SelectLayerByAttribute_management(wet_lyr, "NEW_SELECTION", forested_exp)
arcpy.CopyFeatures_management(wet_lyr, os.path.join(scratch, "wl_Forest"))
forested = os.path.join(scratch, "wl_Forest")

arcpy.SelectLayerByAttribute_management(wet_lyr, "NEW_SELECTION", emergent_exp)
arcpy.CopyFeatures_management(wet_lyr, os.path.join(scratch, "wl_Emerge"))
emergent = os.path.join(scratch, "wl_Emerge")

arcpy.SelectLayerByAttribute_management(wet_lyr, "NEW_SELECTION", other_exp)
arcpy.CopyFeatures_management(wet_lyr, os.path.join(scratch, "wl_Other"))
other = os.path.join(scratch, "wl_Other")

# Make a list of wetland feature classes
arcpy.env.workspace = scratch
wl_list = arcpy.ListFeatureClasses("wl_*")

# Write 1ha waterbodies to scratch.
arcpy.CopyFeatures_management(oneha_lyr, os.path.join(outfolder, "oneha.shp"))
oneha = os.path.join(outfolder, "oneha.shp")
try:
    arcpy.DeleteField_management(oneha,'FCODE')
except:
    pass
try:
    arcpy.DeleteField_management(oneha, 'FDate')
except:
    pass
try:
    arcpy.DeleteField_management(oneha, 'Resolution')
except:
    pass
try:
    arcpy.DeleteField_management(oneha,'GNIS_ID')
except:
    pass
try:
    arcpy.DeleteField_management(oneha, 'GNIS_NAME')
except:
    pass
try:
    arcpy.DeleteField_management(oneha, 'AreaSqKm')
except:
    pass
try:
    arcpy.DeleteField_management(oneha, 'Elevation')
except:
    pass
try:
    arcpy.DeleteField_management(oneha, 'FType' )
except:
    pass
try:
    arcpy.DeleteField_management(oneha, 'ReachCode' )
except:
    pass


table = oneha

# Spatial Join lakes to each wetland type
for wl in wl_list:
    fieldmappings = arcpy.FieldMappings()
    fieldmap_id = arcpy.FieldMap()
    fieldmap_ty = arcpy.FieldMap()
    fieldmap_wetha = arcpy.FieldMap()
    fieldmap_id.addInputField(oneha, "Permanent_") 
    fieldmap_ty.addInputField(wl, "WETLAND_TY")
    fieldmap_wetha.addInputField(wl, "WETLAND_HA")
    fieldmap_wetha.mergeRule = 'SUM'
    fieldmappings.addFieldMap(fieldmap_id)
    fieldmappings.addFieldMap(fieldmap_ty)
    fieldmappings.addFieldMap(fieldmap_wetha)
    arcpy.SpatialJoin_analysis(oneha, wl, os.path.join(scratch, wl[3:]), '', '', fieldmappings)
    outwl = os.path.join(scratch, wl[3:])
    name = os.path.basename(outwl)
    arcpy.AddField_management(outwl, name + "HA", "DOUBLE")
    arcpy.CalculateField_management(outwl, name + "HA", "!WETLAND_HA!", "PYTHON")
    field = name + "HA"
    arcpy.AddField_management(outwl, name + "CNT", "LONG")
    field2 = name + "CNT"
    arcpy.CalculateField_management(outwl, name + "CNT", "!Join_Count!", "PYTHON")
    arcpy.JoinField_management(table, "Permanent_", outwl, "Permanent_", field )
    arcpy.JoinField_management(table, "Permanent_", outwl, "Permanent_", field2 )
    del fieldmappings

       
arcpy.TableToTable_conversion(table, outfolder, "ConnectedWetlands.txt")








    
    







