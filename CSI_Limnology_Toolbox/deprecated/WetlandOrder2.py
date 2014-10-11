# Filename: WetlandOrder.py
# Purpose: Assigns a class to wetlands based on their connectivity to the landscape.


import os
import arcpy
import shutil
from arcpy.da import *

arcpy.CheckOutExtension("DataInteroperability")
arcpy.ResetEnvironments()
arcpy.env.overwriteOutput = "TRUE"

# User input parameters:
rivex = arcpy.GetParameterAsText(0) # A shapefile of rivers that has the "Strahler" field produced by RivEx extension.
nwi = arcpy.GetParameterAsText(1) # NWI feature class
lakes = arcpy.GetParameterAsText(2)
outfolder = arcpy.GetParameterAsText(3) # Location where output gets stored.
ram = "in_memory"

# Environmental Settings
arcpy.ResetEnvironments()
arcpy.env.extent = rivex
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.workspace = ram
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()
arcpy.env.outputCoordinateSystem = albers

# Make a fc of selected wetlands
nwifilter = """ "ATTRIBUTE" LIKE 'P%' """
arcpy.MakeFeatureLayer_management(nwi, "nwi_lyr")
arcpy.SelectLayerByAttribute_management("nwi_lyr", "NEW_SELECTION", nwifilter)
arcpy.CopyFeatures_management("nwi_lyr", "allwetpre")

# Add and calculate CSI ID number field
arcpy.AddField_management("allwetpre", "CSI_ID", "LONG")
arcpy.CalculateField_management("allwetpre", "CSI_ID", "!OBJECTID!", "PYTHON")

# Add field for hectares and calculate
arcpy.AddField_management("allwetpre", "WetHa", "DOUBLE")

# Calculate geometry for wetland hectares.
arcpy.CalculateField_management("allwetpre", "WetHa", "!shape.area@hectares!", "PYTHON")

# Buffer a donut around selected wetland polys 30m
arcpy.Buffer_analysis("allwetpre", "allwet", "30 meters", "OUTSIDE_ONLY")

# Add wetland order field for connected wetlands
arcpy.AddField_management("allwet","WetOrder", "TEXT")

# Spatial join connected wetlands and streams
##################Field Maps########################
fms = arcpy.FieldMappings()
fm_strahlermax = arcpy.FieldMap()
fm_strahlersum = arcpy.FieldMap()
fm_wetorder = arcpy.FieldMap()
fm_wetha = arcpy.FieldMap()
fm_attribute = arcpy.FieldMap()
fm_lengthkm = arcpy.FieldMap()
fm_csi = arcpy.FieldMap()

fm_strahlermax.addInputField(rivex, "Strahler")
fm_strahlersum.addInputField(rivex, "Strahler")
fm_wetorder.addInputField("allwet", "WetOrder")
fm_wetha.addInputField("allwet", "WetHa")
fm_attribute.addInputField("allwet", "ATTRIBUTE")
fm_lengthkm.addInputField(rivex, "LengthKm")
fm_csi.addInputField("allwet", "CSI_ID")

fm_lengthkm.mergeRule = 'Sum'
fm_strahlermax.mergeRule = 'Max'
fm_strahlersum.mergeRule = 'Sum'

lengthkm_name = fm_lengthkm.outputField
lengthkm_name.name = 'StreamKm'
lengthkm_name.aliasName = 'StreamKm'
fm_lengthkm.outputField = lengthkm_name

strahlermax_name = fm_strahlermax.outputField
strahlermax_name.name = 'StrOrdMax'
strahlermax_name.aliasName = 'StrOrdMax'
fm_strahlermax.outputField = strahlermax_name

strahlersum_name = fm_strahlersum.outputField
strahlersum_name.name = 'StrOrdSum'
strahlersum_name.aliasName = 'StrOrdSum'
fm_strahlersum.outputField = strahlersum_name

fms.addFieldMap(fm_strahlermax)
fms.addFieldMap(fm_strahlersum)
fms.addFieldMap(fm_wetorder)
fms.addFieldMap(fm_wetha)
fms.addFieldMap(fm_attribute)
fms.addFieldMap(fm_lengthkm)
fms.addFieldMap(fm_csi)
#####################################################

arcpy.SpatialJoin_analysis("allwet", rivex, "conwetorder", '', '', fms)

# Calculate fields
arcpy.AddField_management("conwetorder", "StreamCnt", "LONG")
arcpy.CalculateField_management("conwetorder","StreamCnt", "!Join_Count!", "PYTHON")
arcpy.DeleteField_management("conwetorder", "Join_Count")

# Create output feature class in a file geodatabase
arcpy.CreateFileGDB_management(outfolder, "WetlandOrder")
outgdb = os.path.join(outfolder, "WetlandOrder.gdb")
arcpy.FeatureClassToFeatureClass_conversion("conwetorder", outgdb, "Buffer30m")
buffer30m = os.path.join(outgdb,"Buffer30m")



outfc = os.path.join(outgdb, "Buffer30m")
try:
    arcpy.DeleteField_management(outfc, "BUFF_DIST")
    arcpy.DeleteField_management(outfc, "ACRES")
    arcpy.DeleteField_management(outfc, "Target_FID")
    arcpy.DeleteField_management(outfc, "Shape_Length")
except:
    pass


# Create Veg field
arcpy.AddField_management(outfc, "Veg", "TEXT")
arcpy.CalculateField_management(outfc, "Veg", "!ATTRIBUTE![:3]", "PYTHON")

# Calculate Veg Field
arcpy.AddField_management(outfc, "VegType", "TEXT")

with arcpy.da.UpdateCursor(outfc, ["Veg", "VegType"]) as cursor:
    for row in cursor:
        if row[0] == "PEM":
            row[1] = "PEMorPAB"
        elif row[0] == "PAB":
            row[1] = "PEMorPAB"
        elif row[0] == "PFO":
            row[1] = "PFO"
        elif row[0] == "PSS":
            row[1] = "PSS"
        else:
            row[1] = "Other"
        cursor.updateRow(row)

del cursor

# Create and calc regime field
# Because there are no place holders where a classification type is omitted in NWI Codes they are hard to separate...
arcpy.AddField_management(outfc, "att_", "TEXT") # ex. "PFO1A_"
arcpy.AddField_management(outfc, "att3", "TEXT") # ex. "PFO*"
arcpy.AddField_management(outfc, "att4", "TEXT") # ex "PFO1*"
arcpy.AddField_management(outfc, "Regime", "TEXT") # This will hold final value. ex. "E"
att_ = '''!ATTRIBUTE! + "____"'''
att3 = "!att_![3]"
att4 = "!att_![4]"
arcpy.CalculateField_management(outfc, "att_", att_, "PYTHON")
arcpy.CalculateField_management(outfc, "att3", att3, "PYTHON")
arcpy.CalculateField_management(outfc, "att4", att4, "PYTHON")

# So we run a cursor...            row[0]  row[1]   row[2]
with arcpy.da.UpdateCursor(outfc, ["att3", "att4", "Regime"]) as cursor:
    for row in cursor:
        if row[0].isdigit():  # if the 4th character is a number (subclass) the next number is the regime
            row[2] = row[1]
        elif row[0].isupper(): # if the 4th character is an upper case letter it is the regime
            row[2] = row[0]
        elif row[0].islower(): # if the 4th character is a lower case letter there's no water regime
            row[2] = "unknown"
        elif row[1] == "/":     # if there are multiple clasifications the regime is unknown
            row[2] = "unknown"
        else:                   # if there's some other odd character the regime is unknown.
            row[2] = "unknown"

        cursor.updateRow(row)

del cursor

# Then we run another cursor...     row[0]  
with arcpy.da.UpdateCursor(outfc, ["Regime"]) as cursor:
    for row in cursor:
        if row[0] == "/":
            row[0] = "unknown"       

        cursor.updateRow(row)

del cursor

arcpy.DeleteField_management(outfc, "att_")
arcpy.DeleteField_management(outfc, "att3")        
arcpy.DeleteField_management(outfc, "att4")


              
 
# Calculate WetOrder from StrOrdSum
with arcpy.da.UpdateCursor(outfc, ["StrOrdSum", "WetOrder"]) as cursor:
    for row in cursor:
        if row[0] == 0:
            row[1] = "Isolated"
        elif row[0] == 1:
            row[1] = "Single"
        elif row[0] == None:
            row[1] = "Isolated"
        else:
            row[1] = "Connected"
        cursor.updateRow(row)

# Delete intermediate veg field
arcpy.DeleteField_management(outfc, "Veg")
try:
    arcpy.DeleteField_management(outfc, "Shape_Length")
    arcpy.DeleteField_management(outfc, "Shape_Area")
except:
    pass

# Change WetOrder to connected if within 30 meters of lake
arcpy.MakeFeatureLayer_management(outfc, "outfc_lyr")
arcpy.SelectLayerByLocation_management("outfc_lyr", "INTERSECT", lakes, "30 meters", "NEW_SELECTION")
arcpy.CopyFeatures_management("outfc_lyr", "con2lake")
arcpy.AddField_management("con2lake", "Con2Lk", "TEXT")
arcpy.CalculateField_management("con2lake", "Con2Lk", "True", "PYTHON")
arcpy.JoinField_management(outfc, "CSI_ID", "con2lake", "CSI_ID", ["Con2Lk"])

with arcpy.da.UpdateCursor(outfc, ["Con2Lk", "WetOrder"]) as lakecursor:
    for row in lakecursor:
        if row[0] == "True":
            row[1] = "Connected"
        lakecursor.updateRow(row)



# Write table to csv file.
def TableToCSV(fc,CSVFile):
    
    fields = [f.name for f in arcpy.ListFields(fc) if f.type <> 'Geometry']
    with open(CSVFile, 'w') as f:
        f.write(','.join(fields)+'\n') # csv headers
        with arcpy.da.SearchCursor(fc, fields) as cursor:
            for row in cursor:
                f.write(','.join([str(r) for r in row])+'\n')
    
if __name__ == '__main__':

    fc = os.path.join(outgdb,"Buffer30m")
    csv = os.path.join(outfolder,"WetlandOrder.csv")
    TableToCSV(fc,csv)


# Join fields from buffer rings back to original polygons.
arcpy.JoinField_management("allwetpre", "CSI_ID", buffer30m, "CSI_ID", ["WetOrder","StrOrdSum","StrOrdMax","StreamCnt","StreamKm", "VegType", "Regime"])
arcpy.FeatureClassToFeatureClass_conversion("allwetpre", outgdb, "WetlandOrder")
    


        
            
                

















