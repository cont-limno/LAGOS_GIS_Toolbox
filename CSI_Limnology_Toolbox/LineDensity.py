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

    # Zones will be coerced to albers, have to check lines though
    arcpy.CopyFeatures_management(zones, "zones_temp")
    if arcpy.Describe(lines).spatialReference.factoryCode != albers.factoryCode:
        arcpy.AddError("Lines feature class does not have desired projection (Albers USGS). Re-project to factory code 102039 and try again.")
        sys.exit(1)

    # Add hectares field to zones
    arcpy.AddField_management("zones_temp", "ZoneAreaHa", "DOUBLE")
    arcpy.CalculateField_management("zones_temp", "ZoneAreaHa", "!shape.area@hectares!", "PYTHON")

    # Perform identity analysis to join fields and crack lines at polygon boundaries
    cu.multi_msg("Cracking lines at polygon boundaries...")
    arcpy.Identity_analysis(lines, "zones_temp", "lines_identity")
    cu.multi_msg("Cracking lines complete.")

    # Recalculate lengths
    arcpy.AddField_management("lines_identity", "LengthM", "DOUBLE")
    arcpy.CalculateField_management("lines_identity", "LengthM", '!shape.length@meters!', "PYTHON")

    # Summarize statistics by zone
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

    arcpy.CopyRows_management("length_in_zone", out_table)

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

