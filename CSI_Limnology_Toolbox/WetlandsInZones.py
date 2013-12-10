# Name:WetlandsInZones.py
# Purpose: Gives a count and area in hectares of wetlands intersecting zones.
# Author: Scott Stopyak
# Created: 19/11/2013
# Copyright:(c) Scott Stopyak 2013
# Licence: Distributed under the terms of GNU GPL
#_______________________________________________________________________________

import arcpy, os

# Parameters
infolder = arcpy.GetParameterAsText(0) # Workspace with zone feature classes
idfield = arcpy.GetParameterAsText(1) # Field that is the unique id for every extent poly
wetlands = arcpy.GetParameterAsText(2) # Wetland polygon feature class
topoutfolder = arcpy.GetParameterAsText(3) # Output folder
arcpy.env.overwriteOutput = True

# Create output geodatabase in outfolder
try:
    arcpy.CreateFileGDB_management(topoutfolder, "WetlandsByZone")
except:
    pass
outfolder = os.path.join(topoutfolder, "WetlandsByZone.gdb")

# Add WetlandHa field if it doesn't exist
try:
    arcpy.AddField_management(wetlands, "WetlandHa", "DOUBLE")
except:
    pass
expha = "!shape.area@hectares!"
arcpy.CalculateField_management(wetlands, "WetlandHa", expha, "PYTHON")
arcpy.RefreshCatalog(wetlands)

# Set in memory as workspace. Intermediate output will be held in RAM.
mem = "in_memory"
arcpy.env.workspace = mem
arcpy.env.overwriteOutput = True

# Make wetlands in memory.
exp = """"ATTRIBUTE" LIKE 'P%'"""
arcpy.Select_analysis(wetlands, "wetlands", exp)
arcpy.RefreshCatalog(mem)

# List extent feature classes
fcs = []
for root, dirs, files in arcpy.da.Walk(infolder):
    for file in files:
        fcs.append(os.path.join(root,file))

# Set workspace
arcpy.env.workspace = mem

# Spatial Join the wetlands to each extent
for fc in fcs:
    name = os.path.basename(fc)
    fms = arcpy.FieldMappings()
    fmid = arcpy.FieldMap()
    fmha = arcpy.FieldMap()
    fmid.addInputField(fc, idfield)
    fmha.addInputField("wetlands", "WetlandHa")
    fmha.mergeRule = 'Sum'
    fms.addFieldMap(fmid)
    fms.addFieldMap(fmha)
    arcpy.SpatialJoin_analysis(fc, wetlands, os.path.join(outfolder,\
     "Table_" + name + "_Wetlands"),'','',fms)


# Export feature classes to dbfs
outlist = []
for root, dirs, files in arcpy.da.Walk(outfolder):
    for file in files:
        outlist.append(os.path.join(root,file))
for f in outlist:
    arcpy.TableToDBASE_conversion(f,topoutfolder)

