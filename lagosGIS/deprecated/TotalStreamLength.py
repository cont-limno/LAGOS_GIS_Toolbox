# Filename: TotalStreamLength.py
# Purpose: Calculate lengths of all streams in polygons.

import os, arcpy

# User defined parameters:
nhd = arcpy.GetParameterAsText(0) # NHD Subregion fgdb. This must cover the polygons you want to calculate.
poly = arcpy.GetParameterAsText(1) # Polygon feature class that must be in EPSG 102039 (albers usgs version)
outfolder = arcpy.GetParameterAsText(2) # Outfolder

# Starting Environments:
arcpy.ResetEnvironments()
arcpy.env.overwriteOutput = "TRUE"
arcpy.env.workspace = nhd

# Naming Convention
subregion_number = os.path.basename(nhd)
nhdsubregion = subregion_number[4:8]

# Create output folder
if not os.path.exists(os.path.join(outfolder, "StreamLength")):
    os.mkdir(os.path.join(outfolder, "TotalStreamLength_" + nhdsubregion))

finalfolder = os.path.join(outfolder, "TotalStreamLength_" + nhdsubregion)

# Project NHDFlowline
nad83 = arcpy.SpatialReference()
nad83.factoryCode = 4269
nad83.create()
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create
nhdflowline = os.path.join(nhd, "Hydrography", "NHDFlowline")
arcpy.Project_management(nhdflowline, os.path.join(outfolder, "flowline.shp"), albers, '', nad83)
flowline = os.path.join(outfolder, "flowline.shp")

# Make poly for subregion extent.
subregion_number = os.path.basename(nhd)
nhdsubregion = subregion_number[4:8]
wbd = os.path.join(nhd, "WBD", "WBD_HU4")
arcpy.MakeFeatureLayer_management(wbd, os.path.join(outfolder, "wbd.lyr"))
wbd_lyr = os.path.join(outfolder, "wbd.lyr")
field = "HUC_4"
where = '"' + field + '" = ' + "'" + str(nhdsubregion) + "'"
arcpy.SelectLayerByAttribute_management(wbd_lyr, "NEW_SELECTION", where)
arcpy.CopyFeatures_management(wbd_lyr, os.path.join(outfolder, "extent.shp"))
extentnad = os.path.join(outfolder, "extent.shp")
arcpy.Project_management(extentnad, os.path.join(outfolder, "extentalbers.shp"), albers, '', nad83)
extent = os.path.join(outfolder, "extentalbers.shp")

# Intersect flowlines and polygons to crack lines.
arcpy.Intersect_analysis([poly, flowline], os.path.join(outfolder, "crackedlines.shp"), "ONLY_FID", '', "LINE")
cracked = os.path.join(outfolder, "crackedlines.shp")

# Add field and calculate length of stream segments
length_exp = '''round(!shape.length@kilometers!,3)'''
arcpy.AddField_management(cracked, "StLengthKm", "DOUBLE")
arcpy.CalculateField_management(cracked, "StLengthKm", length_exp, "PYTHON")

# Create a field map for the upcoming spatial join.
fieldmappings = arcpy.FieldMappings()
fieldmappings.addTable(poly)
fieldmap_StLengthKm = arcpy.FieldMap()
StLengthKm = "StLengthKm"
fieldmap_StLengthKm.addInputField(cracked, StLengthKm)
fieldmap_StLengthKm.mergeRule = 'Sum'
fieldmappings.addFieldMap(fieldmap_StLengthKm)

# 1 to 1 Spatial join of polygons and cracked flowlines, summarizing Length_km field.
arcpy.SpatialJoin_analysis(poly, cracked, os.path.join(outfolder, "joinedpoly.shp"), "JOIN_ONE_TO_ONE", "", fieldmappings, "INTERSECT")

joined = os.path.join(outfolder, "joinedpoly.shp")

# Eliminate those polys that are outside of the AOI but were included by way of small stream dangles.
arcpy.MakeFeatureLayer_management(joined, os.path.join(outfolder, "joined.lyr"))
joined_lyr = os.path.join(outfolder, "joined.lyr")
arcpy.SelectLayerByLocation_management(joined_lyr, "HAVE_THEIR_CENTER_IN", extent, '', "NEW_SELECTION")
arcpy.CopyFeatures_management(joined_lyr, os.path.join(finalfolder, os.path.basename(poly)))

# Refresh Catalog and clean up intermediate data (unless esri has it locked up).
arcpy.RefreshCatalog(outfolder)
try:
    intdata = [cracked,extent,extentnad,flowline,joined]
    for f in intdata:
        arcpy.Delete_management(f)
except:
    pass
arcpy.RefreshCatalog(outfolder)




                              
                                  


    
    




