# Filename: LineDensity.py
# Creator: Scott Stopyak, 2013
# This tool produces a table with length of lines in meters, area of polygons in hectares and line density expressed as meters per ha.
# Copyright (c) Scott Stopyak, 2013
# Distributed under the terms of GNU GPL
#____________________________________________________________________________________________________________________________________

import arcpy, os
from arcpy.sa import *
arcpy.CheckOutExtension('Spatial')

def line_density(zones, zonefield, lines, topoutfolder):
    # Make output folder
    name = "LineDensity_" + os.path.splitext(os.path.basename(zones))[0]
    if not os.path.exists(os.path.join(topoutfolder, name)):
        os.mkdir(os.path.join(topoutfolder, name))
    outfolder = os.path.join(topoutfolder, name)

    # Environmental Settings
    mem = "in_memory"
    arcpy.env.workspace = mem
    arcpy.env.overwriteOutput = True
    albers = arcpy.SpatialReference()
    albers.factoryCode = 102039
    albers.create()
    arcpy.env.outputCoordinateSystem = albers
    arcpy.RefreshCatalog(topoutfolder)
    # Create scratch workspace
    try:
        arcpy.CreateFileGDB_management(outfolder, "scratch")

    except:
        pass
    scratch = os.path.join(outfolder, "scratch.gdb")
    arcpy.RefreshCatalog(outfolder)

    # Project features to memory workspace
    zone_sr = arcpy.Describe(zones)
    spatialRefZones = zone_sr.SpatialReference
    arcpy.Project_management(zones, os.path.join(scratch, "zones"), albers,'',spatialRefZones)
    lines_sr = arcpy.Describe(lines)
    spatialRefLines = lines_sr.SpatialReference
    arcpy.Project_management(lines,os.path.join(scratch, "lines"), albers,'',spatialRefLines)
    arcpy.env.workspace = scratch
    arcpy.RefreshCatalog(topoutfolder)

    # Add hectares field to zones
    arcpy.AddField_management("zones", "ZoneAreaHa", "DOUBLE")
    arcpy.CalculateField_management("zones", "ZoneAreaHa", "!shape.area@hectares!", "PYTHON")
    arcpy.RefreshCatalog(topoutfolder)

    # Perform identity analysis to join fields and crack roads at polygon boundaries
    try:
        arcpy.Identity_analysis("lines", "zones", "lines_identity")
    except:
        pass
        arcpy.RefreshCatalog(topoutfolder)
        try:
            arcpy.Identity_analysis("lines", "zones", "lines_identity")
        except:
            arcpy.AddMessage("The output location is locking up and not allowing output to be written to it. Try it again with antivirus off and/or in a different location.")
        pass

    # Recalculate lengths
    arcpy.AddField_management("lines_identity", "LengthM", "DOUBLE")
    arcpy.CalculateField_management("lines_identity", "LengthM", '!shape.length@meters!', "PYTHON")

    # Summarize statistics by zone
    name = os.path.splitext(os.path.basename(zones))[0]
    arcpy.Statistics_analysis("lines_identity", os.path.join(outfolder, "LineDensity_" + name), "LengthM SUM", zonefield)
    table = arcpy.CreateUniqueName("LineDensity_" + name, outfolder)

    # Join ZoneAreaHa to table
    arcpy.JoinField_management(table, zonefield, "zones" , zonefield, ["ZoneAreaHa"])

    # Delete rows in table with zero for zone area
    with arcpy.da.UpdateCursor(table, ["ZONEAREAHA"]) as cursor:
        for row in cursor:
            if row[0] == 0:
                cursor.deleteRow()

    # Add Density field and calc
    arcpy.AddField_management(table, "Density", "DOUBLE",'','','','',"NULLABLE")
    exp = "!SUM_LengthM! / !ZONEAREAHA!"
    arcpy.CalculateField_management(table, "Density", exp, "PYTHON")
    arcpy.DeleteField_management(table, "FREQUENCY")
    try:
        arcpy.Delete_management(scratch)
    except:
        pass
    arcpy.RefreshCatalog(topoutfolder)

    return table

def main():
    # Parameters
    zones = arcpy.GetParameterAsText(0)
    zonefield = arcpy.GetParameterAsText(1)
    lines = arcpy.GetParameterAsText(2)
    topoutfolder =  arcpy.GetParameterAsText(3)
    line_density(zones, zonefield, lines, topoutfolder)


