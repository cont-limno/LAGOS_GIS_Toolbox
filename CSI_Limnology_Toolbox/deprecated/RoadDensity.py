# Filename: RoadDensity4.py

import arcpy, os
from arcpy.sa import *

# Parameters
zones = arcpy.GetParameterAsText(0)
zonefield = arcpy.GetParameterAsText(1)
rds = arcpy.GetParameterAsText(2)
outfolder =  arcpy.GetParameterAsText(3)

# Environmental Settings
mem = "in_memory"
arcpy.env.workspace = mem
arcpy.env.overwriteOutput = True

# Copy features to memory
arcpy.CopyFeatures_management(zones, "zones")
arcpy.CopyFeatures_management(rds, "rds")

# Add length field to rds (meters)
arcpy.AddField_management("rds", "RdLengthM", "DOUBLE")
arcpy.CalculateField_management("rds", "RdLengthM", "!shape.length@meters!", "PYTHON")

# Add hectares field to zones
arcpy.AddField_management("zones", "ZoneAreaHa", "DOUBLE")
arcpy.CalculateField_management("zones", "ZoneAreaHa", "!shape.area@hectares!", "PYTHON")

# Perform identity analysis to join fields and crack roads at polygon boundaries
arcpy.Identity_analysis("rds", "zones", "rds_identity")

# Summarize statistics by zone
name = os.path.splitext(os.path.basename(zones))[0]
arcpy.Statistics_analysis("rds_identity", os.path.join(outfolder, name + "_RdDensity"), "RdLengthM SUM", zonefield)
table = os.path.join(outfolder, name + "_RdDensity")

# Join ZoneAreaHa to table
arcpy.JoinField_management(table, zonefield, "zones" , zonefield, ["ZoneAreaHa"])

# Add RdDensity field and calc
arcpy.AddField_management(table, "RdDensity", "DOUBLE",'','','','',"NULLABLE")
exp = "!SUM_RDLENGTHM! / !ZONEAREAHA!"

with arcpy.da.UpdateCursor(table, ["ZONEAREAHA"]) as cursor:
    for row in cursor:
        if row[0] == 0:
            cursor.deleteRow()

arcpy.CalculateField_management(table, "RdDensity", exp, "PYTHON")           


