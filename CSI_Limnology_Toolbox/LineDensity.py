# Filename: LineDensity.py
# Creator: Scott Stopyak, 2013
# This tool produces a table with length of lines in meters, area of polygons in hectares and line density expressed as meters per ha.
# Copyright (c) Scott Stopyak, 2013
# Distributed under the terms of GNU GPL
#____________________________________________________________________________________________________________________________________
import os
import arcpy
import csiutils as cu


def line_density(zones, zonefield, lines, out_table):
    # Make output folder
##    name = "LineDensity_" + os.path.splitext(os.path.basename(zones))[0]
##    outfolder = os.path.join(topoutfolder, name)
##    if not os.path.exists(outfolder):
##        os.mkdir(outfolder)


    # Environmental Settings
    ws = "in_memory"
    arcpy.env.workspace = ws
    albers = arcpy.SpatialReference(102039)
    arcpy.env.outputCoordinateSystem = albers
    arcpy.env.extent = zones

    # Create scratch workspace
##    try:
##        arcpy.CreateFileGDB_management(outfolder, "scratch")
##
##    except:
##        pass
##    scratch = os.path.join(outfolder, "scratch.gdb")
##    arcpy.RefreshCatalog(outfolder)

    # Project features to memory workspace
##    zone_sr = arcpy.Describe(zones)
##    spatialRefZones = zone_sr.SpatialReference
##    arcpy.Project_management(zones, os.path.join(scratch, "zones"), albers,'',spatialRefZones)
##    lines_sr = arcpy.Describe(lines)
##    spatialRefLines = lines_sr.SpatialReference
##    arcpy.Project_management(lines,os.path.join(scratch, "lines"), albers,'',spatialRefLines)
##    arcpy.env.workspace = scratch
##    arcpy.RefreshCatalog(topoutfolder)

    arcpy.CopyFeatures_management(zones, "zones_temp")

    # Add hectares field to zones
    arcpy.AddField_management("zones_temp", "ZoneAreaHa", "DOUBLE")
    arcpy.CalculateField_management("zones_temp", "ZoneAreaHa", "!shape.area@hectares!", "PYTHON")

    # Perform identity analysis to join fields and crack lines at polygon boundaries
##    try:
    cu.multi_msg("Cracking lines at polygon boundaries...")
    arcpy.Identity_analysis(lines, "zones_temp", "lines_identity")
    cu.multi_msg("Cracking lines complete.")
##    except:
##        pass
##        arcpy.RefreshCatalog(topoutfolder)
##        try:
##            arcpy.Identity_analysis("lines", "zones", "lines_identity")
##        except:
##            arcpy.AddMessage("The output location is locking up and not allowing output to be written to it. Try it again with antivirus off and/or in a different location.")
##        pass

    # Recalculate lengths
    arcpy.AddField_management("lines_identity", "LengthM", "DOUBLE")
    arcpy.CalculateField_management("lines_identity", "LengthM", '!shape.length@meters!', "PYTHON")

    # Summarize statistics by zone
##    name = os.path.splitext(os.path.basename(zones))[0]
##    table = arcpy.CreateUniqueName("LineDensity_" + name, outfolder)
    arcpy.Statistics_analysis("lines_identity", "length_in_zone", "LengthM SUM", zonefield)


    # Join ZoneAreaHa to table
    arcpy.JoinField_management("length_in_zone", zonefield, "zones_temp" , zonefield, "ZoneAreaHa")

    # Delete rows in table with zero for zone area
    with arcpy.da.UpdateCursor("length_in_zone", "ZoneAreaHa") as cursor:
        for row in cursor:
            if row[0] == 0:
                cursor.deleteRow()

    # Add Density field and calc
    arcpy.AddField_management("length_in_zone", "Density", "DOUBLE",'','','','',"NULLABLE")
    exp = "!SUM_LengthM! / !ZONEAREAHA!"
    arcpy.CalculateField_management("length_in_zone", "Density", exp, "PYTHON")
    arcpy.DeleteField_management("length_in_zone", "FREQUENCY")
##    try:
##        arcpy.Delete_management(scratch)
##    except:
##        pass
##    arcpy.RefreshCatalog(topoutfolder)

    arcpy.CopyRows_management("length_in_zone", out_table)

    # SAVING the lines fc if necessary in memory because it is large
    for tempitem in ['zones_temp', 'lines_identity', 'length_in_zone']:
        arcpy.Delete_management(tempitem)
    return out_table

def main():
    # Parameters
    zones = arcpy.GetParameterAsText(0)
    zonefield = arcpy.GetParameterAsText(1)
    lines = arcpy.GetParameterAsText(2)
    out_table =  arcpy.GetParameterAsText(3)
    line_density(zones, zonefield, lines, out_table)

def test():
    # Parameters
    zones = 'C:/GISData/Master_Geodata/MasterGeodatabase2014.gdb/EDU'
    zonefield = 'ZoneID'
    lines = 'C:/GISData/Master_Geodata/MasterGeodatabase2014.gdb/Streams'
    out_table = 'C:/GISData/Scratch/Scratch.gdb/test_linedensity_FULL'
    line_density(zones, zonefield, lines, out_table)

if __name__ == '__main__':
    main()

