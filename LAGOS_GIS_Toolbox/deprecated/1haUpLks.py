# Filename: 1haUpLks.py

import arcpy, os, sys
#
# User-defined parameters:
cws = arcpy.GetParameterAsText(0) # watersheds to intersect (e.g. Cumulative Watershed)
nhd = arcpy.GetParameterAsText(1) # nhd subregion geodatabase
outfolder = arcpy.GetParameterAsText(2) # folder for output

# Setup environments and variables
arcpy.ResetEnvironments()
mem = "in_memory"
arcpy.env.workspace = nhd
arcpy.env.overwriteOutput = "True"
waterbody = os.path.join(nhd, "Hydrography", "NHDWaterbody")

# Naming Convention
subregion_number = os.path.basename(nhd)
subregion = subregion_number[4:8]

# Create a fc of one hectare lakes:
exp1ha = '''"AreaSqKm" >=0.01 AND ("FCode" = 39000 OR "FCode" = 39004 OR\
"FCode" = 39009 OR "FCode" = 39010 OR "FCode" = 39011 OR "FCode" = 39012 OR "FCode" = 43600 OR "FCode" = 43613 OR\
"FCode" = 43615 OR "FCode" = 43617 OR "FCode" = 43618 OR "FCode" = 43619 OR "FCode" = 43621 OR ("FCode" = 43601 AND "AreaSqKm" >=0.1 ))'''
arcpy.MakeFeatureLayer_management(waterbody, os.path.join(outfolder, "oneha.lyr"), exp1ha)
oneha_lyr = os.path.join(outfolder, "oneha.lyr")
arcpy.CopyFeatures_management(oneha_lyr, os.path.join(mem, "onehalakes"))
onehalakes = os.path.join(mem, "onehalakes")



# Spatial join cumulative watersheds to 1 hectare and larger lakes
# Field mapping:
# Add empty field map and mapping obects.
fms = arcpy.FieldMappings()
fm_areasqkm = arcpy.FieldMap()
fm_nhdid = arcpy.FieldMap()

# Add the fields from feature classes to the empty field map objects
fm_areasqkm.addInputField(onehalakes, "AreaSqKm")
fm_nhdid.addInputField(cws, "NHD_ID")

# Add a merge rule to summarize the "AreaSqKm" field from the lakes
fm_areasqkm.mergeRule = 'Sum'

# Set output names for fields
fm_areasqkm_name = fm_areasqkm.outputField
fm_areasqkm_name.name = 'T10ha_km2'
fm_areasqkm.outputField = fm_areasqkm_name

fm_nhdid_name = fm_nhdid.outputField
fm_nhdid_name.name = 'NHD_ID'
fm_nhdid.outputField = fm_nhdid_name

# Add Field Maps to Field Mappings object
fms.addFieldMap(fm_areasqkm)
fms.addFieldMap(fm_nhdid)

# Spatial Join
arcpy.SpatialJoin_analysis(cws, onehalakes, os.path.join(outfolder, "CalconeHaLk" + subregion + ".shp"), '', '', fms, "HAVE_THEIR_CENTER_IN")

sj = os.path.join(outfolder, "CalconeHaLk" + subregion + ".shp")

# Change name of join_count to T10ha (the total 1 ha lakes with their center in that cumulative watershed)
arcpy.AddField_management(sj, "T10ha", "SHORT")
arcpy.CalculateField_management(sj, "T10ha", '!Join_Count!', "PYTHON")







