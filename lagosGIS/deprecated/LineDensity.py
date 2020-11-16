# Filename: LineDensity.py
# Creator: Scott Stopyak, 2013
# This tool produces a table with length of lines in meters, area of polygons in hectares and line density expressed as meters per ha.
# Copyright (c) Scott Stopyak, 2013
# Distributed under the terms of GNU GPL
#____________________________________________________________________________________________________________________________________
import os
import sys
import arcpy
import lagosGIS
from lagosGIS import select_fields as lagosGIS_select_fields


def line_density(zones, zonefield, lines, out_table, interest_selection_expr):
    # Make output folder
##    name = "LineDensity_" + os.path.splitext(os.path.basename(zones))[0]
##    outfolder = os.path.join(topoutfolder, name)
##    if not os.path.exists(outfolder):
##        os.mkdir(outfolder)

    # Environmental Settings
    ws = "in_memory"

    if interest_selection_expr:
        arcpy.MakeFeatureLayer_management(lines, "selected_lines", interest_selection_expr)
    else:
        arcpy.MakeFeatureLayer_management(lines, "selected_lines")

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
    lagosGIS.multi_msg("Cracking lines at polygon boundaries...")
    arcpy.Identity_analysis("selected_lines", "zones_temp", "lines_identity")
    lagosGIS.multi_msg("Cracking lines complete.")

    # Recalculate lengths
    arcpy.AddField_management("lines_identity", "LengthM", "DOUBLE")
    arcpy.CalculateField_management("lines_identity", "LengthM", '!shape.length@meters!', "PYTHON")

    # Summarize statistics by zone
    arcpy.Statistics_analysis("lines_identity", "length_in_zone", "LengthM SUM", zonefield)


    # Join ZoneAreaHa to table
    arcpy.JoinField_management("length_in_zone", zonefield, "zones_temp" , zonefield, "ZoneAreaHa")

    # Delete rows in table with zero for zone area
##    with arcpy.da.UpdateCursor("length_in_zone", "ZoneAreaHa") as cursor:
##        for row in cursor:
##            if row[0] is None:
##                cursor.deleteRow()

    # Rename length field
    arcpy.AlterField_management("length_in_zone", "SUM_LengthM", "m", clear_field_alias=True)

    # Add Density field and calc
    arcpy.AddField_management("length_in_zone", "mperha", "DOUBLE")
    exp = "!m! / !ZONEAREAHA!"
    arcpy.CalculateField_management("length_in_zone", "mperha", exp, "PYTHON")

    # Clean up the table--one row per input zone, nulls do mean 0 here, exclude streams outside zones
    lagosGIS.one_in_one_out("length_in_zone", zones, zonefield, "one_in_one_out")
    arcpy.TableSelect_analysis("one_in_one_out", "selected_fields", "{} <> ''".format(zonefield))
    lagosGIS_select_fields("selected_fields", out_table, [zonefield, 'm', 'mperha'])

    lagosGIS.redefine_nulls(out_table, ['m', 'mperha'], [0, 0])



    for tempitem in ['zones_temp', 'lines_identity', 'length_in_zone']:
        arcpy.Delete_management(tempitem)

    return out_table

def main():
    # Parameters
    zones = arcpy.GetParameterAsText(0)
    zonefield = arcpy.GetParameterAsText(1)
    lines = arcpy.GetParameterAsText(2)
    out_table =  arcpy.GetParameterAsText(4)
    interest_selection_expr = arcpy.GetParameterAsText(3)
    line_density(zones, zonefield, lines, out_table, interest_selection_expr)

def test():
    # Parameters
    test_gdb = '../TestData_0411.gdb'
    zones = os.path.join(test_gdb, 'HU12')
    zonefield = 'ZoneID'
    lines = os.path.join(test_gdb, 'Streams')
    out_table = 'C:/GISData/Scratch/Scratch.gdb/test_line_density'
    line_density(zones, zonefield, lines, out_table, '')

if __name__ == '__main__':
    main()

