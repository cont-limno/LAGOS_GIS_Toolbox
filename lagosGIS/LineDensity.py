# Filename: LineDensity.py
# Creator: Scott Stopyak, 2013
# This tool produces a table with length of lines in meters, area of polygons in hectares and line density expressed as meters per ha.
# Copyright (c) Scott Stopyak, 2013
# Distributed under the terms of GNU GPL
#____________________________________________________________________________________________________________________________________
import os
import arcpy
import csiutils as cu


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
    cu.multi_msg("Cracking lines at polygon boundaries...")
    arcpy.Identity_analysis("selected_lines", "zones_temp", "lines_identity")
    cu.multi_msg("Cracking lines complete.")

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

    # Add Density field and calc
    arcpy.AddField_management("length_in_zone", "Density_MperHA", "DOUBLE",'','','','',"NULLABLE")
    exp = "!SUM_LengthM! / !ZONEAREAHA!"
    arcpy.CalculateField_management("length_in_zone", "Density_MperHA", exp, "PYTHON")

    cu.one_in_one_out("length_in_zone", ['SUM_LengthM', 'Density_MperHA'], zones, zonefield, out_table)
    cu.redefine_nulls(out_table, ['SUM_LengthM', 'Density_MperHA'], [0, 0])


##    # Join to the original table
##    keep_fields = ["ZoneID", "SUM_LengthM", "Density_MperHA"]
##    arcpy.JoinField_management('zones_temp', zonefield, "length_in_zone", zonefield, keep_fields[1:])
##
##    # Select only null records and change to 0
##    arcpy.MakeFeatureLayer_management('zones_temp', 'zones_temp_lyr')
##    arcpy.SelectLayerByAttribute_management('zones_temp_lyr', "NEW_SELECTION", '''"SUM_LengthM" is null''')
##    fields_to_calc = ["SUM_LengthM", "Density_MperHA"]
##    for f in fields_to_calc:
##        arcpy.CalculateField_management('zones_temp_lyr', f, 0, "PYTHON")
##
##    #Delete all the fields that aren't the ones I need
##    keep_fields = ["ZoneID", "SUM_LengthM", "Density_MperHA"]
##    all_fields = [f.name for f in arcpy.ListFields('zones_temp_lyr')]
##    for f in all_fields:
##        if f not in keep_fields:
##            try:
##                arcpy.DeleteField_management('zones_temp_lyr', f)
##            except:
##                continue
##    arcpy.SelectLayerByAttribute_management('zones_temp_lyr', 'CLEAR_SELECTION')
##
##    arcpy.CopyRows_management('zones_temp_lyr', out_table)

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

