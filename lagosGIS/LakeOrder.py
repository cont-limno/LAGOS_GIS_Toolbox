# Filename: LakeOrder.py
# Purpose: Assigns a lake order classification to a lake shapefile using a RivEx generated river shapefile
#          with stream order.

import os
import arcpy
import shutil


# User inputs:
rivex = arcpy.GetParameterAsText(0) # A shapefile of rivers that has the "Strahler" field produced by RivEx extension.
csilakes = arcpy.GetParameterAsText(1) # A shapefile of CSILakes.
nwi = arcpy.GetParameterAsText(2) # NWI shapefile
topoutfolder = arcpy.GetParameterAsText(3) # Location where output gets stored.

# Make output folder
foldername = os.path.splitext(os.path.basename(csilakes))[0]
if not os.path.exists(os.path.join(topoutfolder,foldername)):
    os.mkdir(os.path.join(topoutfolder,foldername))
outfolder = os.path.join(topoutfolder,foldername)

# Environmental settings
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.extent = csilakes
arcpy.env.overwriteOutput = "TRUE"
mem = "in_memory"
arcpy.env.workspace = mem
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()
arcpy.env.outputCoordinateSystem = albers
arcpy.env.extent = csilakes

# Select non-artificial rivers that intersect lakes and make layer
exp1 = '''"FType" = 334 OR "FType" = 336 OR "FType" = 460 OR "FType" = 566'''
arcpy.MakeFeatureLayer_management(rivex, "streamslyr", exp1)
arcpy.SelectLayerByLocation_management("streamslyr", "INTERSECT", csilakes, '', "NEW_SELECTION")
arcpy.CopyFeatures_management("streamslyr", "streams")

# Make points from the start vertices of intersecting stream segments.
arcpy.FeatureVerticesToPoints_management("streams", "potdrains", "START")

# Select from potential drain points those that intersect lakes.
arcpy.MakeFeatureLayer_management("potdrains", "potdrainslyr")
arcpy.SelectLayerByLocation_management("potdrainslyr", "", csilakes)
arcpy.CopyFeatures_management("potdrainslyr", "drainpts")

# Spatial join
basename = os.path.splitext(os.path.basename(csilakes))[0]
fms = arcpy.FieldMappings()
fmcon = arcpy.FieldMap()
fmid = arcpy.FieldMap()
fmstrahler = arcpy.FieldMap()

fmcon.addInputField(csilakes, "Connection")
fmid.addInputField(csilakes, "Permanent_")
fmstrahler.addInputField("drainpts", "Strahler")

fmid_name = fmid.outputField
fmid_name.name = 'NHD_ID'
fmid_name.aliasName = 'NHD_ID'
fmid.outputField = fmid_name

fmstrahler.mergeRule = 'Max'

fms.addFieldMap(fmcon)
fms.addFieldMap(fmid)
fms.addFieldMap(fmstrahler)

join = "%s" % (basename)
arcpy.SpatialJoin_analysis(csilakes, "drainpts", join, '', '', fms)

# Assign Headwater Lakes a value of zero in the Strahler field.
hwfield = "Strahler"
cursor = arcpy.UpdateCursor(join, """"Connection" = 'Headwater'""")
for row in cursor:
    # Change to zero
    row.setValue(hwfield,0)
    cursor.updateRow(row)

del row
del cursor

# Assign Isolated Lakes a value of -3 in the Strahler field.
seepfield = "Strahler"
cursor = arcpy.UpdateCursor(join, """"Connection" = 'Isolated'""")
for row in cursor:
    # Change to neg 3
    row.setValue(seepfield,-3)
    cursor.updateRow(row)

del row
del cursor


# Select those isolated lakes that are connected to connected lakes by wetlands
arcpy.MakeFeatureLayer_management(join, "joinlyr")
arcpy.SelectLayerByAttribute_management("joinlyr", "NEW_SELECTION", """"Connection" = 'Isolated'""")
arcpy.CopyFeatures_management("joinlyr", "isolakes")
arcpy.SelectLayerByAttribute_management("joinlyr", "NEW_SELECTION", """"Connection" = 'Isolated'""")
arcpy.SelectLayerByAttribute_management("joinlyr", "SWITCH_SELECTION", """"Connection" = 'Isolated'""")
arcpy.CopyFeatures_management("joinlyr", "conlakes")
arcpy.MakeFeatureLayer_management(nwi, "nwilyr")

arcpy.SelectLayerByLocation_management("nwilyr", "INTERSECT", "isolakes", '', "NEW_SELECTION")
arcpy.SelectLayerByAttribute_management("nwilyr", "SUBSET_SELECTION", """"ATTRIBUTE" LIKE 'P%' AND "WETLAND_TY" <> 'Freshwater Pond'""")
arcpy.SelectLayerByLocation_management("nwilyr", "INTERSECT", rivex, '', "SUBSET_SELECTION")
arcpy.Dissolve_management("nwilyr", "conwetlands")

arcpy.SelectLayerByLocation_management("joinlyr", "INTERSECT", "conwetlands", '', "NEW_SELECTION")
arcpy.SelectLayerByAttribute_management("joinlyr", "SUBSET_SELECTION", """"Connection" = 'Isolated'""")
arcpy.CalculateField_management("joinlyr", "Strahler", "-2", "PYTHON")
arcpy.SelectLayerByAttribute_management("joinlyr", "CLEAR_SELECTION")
arcpy.CopyFeatures_management("joinlyr", "preout")

# Classify lakes from "preout" that are only intersected by intermittent streams.
arcpy.MakeFeatureLayer_management(rivex, "perennial", """"FCode" = 46000 OR\
"FCode" = 46006 OR "FCode" = 33600 OR "FCode" = 33400 OR "FCode" = 33601""")

arcpy.MakeFeatureLayer_management("preout", "poslakeorder")

arcpy.SelectLayerByLocation_management("poslakeorder", "INTERSECT", "perennial", '', "NEW_SELECTION")
arcpy.SelectLayerByLocation_management("poslakeorder", "INTERSECT", "perennial", '', "SWITCH_SELECTION")
arcpy.SelectLayerByAttribute_management("poslakeorder", "SUBSET_SELECTION", """"Strahler" >= 0""")
arcpy.CalculateField_management("poslakeorder", "Strahler", "-1", "PYTHON")
arcpy.SelectLayerByAttribute_management("poslakeorder", "CLEAR_SELECTION")
arcpy.CopyFeatures_management("poslakeorder", os.path.join(outfolder, "LakeOrder_" + basename + ".shp"))
lakeorder = os.path.join(outfolder, "LakeOrder_" + basename + ".shp")

# Clear in memory workspace
for root, dirs, files in arcpy.da.Walk(mem):
    for file in files:
        arcpy.DeleteFeatures_management(file)

# Change field name from Strahler to LkOrder
arcpy.AddField_management(lakeorder, "LkOrder", "SHORT")
exp = "!Strahler!"
arcpy.CalculateField_management(lakeorder, "LkOrder", exp, "PYTHON")
deletefields = ['Strahler', 'Connection', 'Join_Count', 'TARGET_FID']
try:
    arcpy.DeleteField_management(lakeorder, deletefields)
except:
    pass





