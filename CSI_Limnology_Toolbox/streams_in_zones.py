#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      smithn78
#
# Created:     30/06/2014
# Copyright:   (c) smithn78 2014
# Licence:     <your licence>
#-------------------------------------------------------------------------------

def main():
    pass

if __name__ == '__main__':
    main()
# Lakes in Zones, the new one
# this does all the lake stuff at once for a given extent
import os
import arcpy
import LineDensity
import csiutils as cu

def streams_in_zones(zones_fc, zone_field, streams_fc, output_table):

    arcpy.env.workspace = 'in_memory'

    # this bit enforces the correct ftype restriction just in case
    # geodata doesn't have this filtered already
    # this won't be as good as doing it before hand because it's
    # not sophisticated enough to take out the artificial lines going
    # through lakes
    need_selection = False
    with arcpy.da.SearchCursor(streams_fc, ["FType"]) as cursor:
            for row in cursor:
                if row[0] == 566:
                    need_selection = True

    if need_selection:
        whereClause = """"FType" <> 566"""
        arcpy.Select_analysis(temp_lakes, "no_coastlines", whereClause)
        streams_fc = os.path.join(arcpy.env.workspace, "no_coastlines")


    selections = ['',
                """"Strahler" <= 3""",
                """"Strahler" > 3 AND "Strahler" <= 6""",
                """"Strahler" > 6""",
                ]
    temp_tables = ['Streams', 'Headwaters', 'Midreaches', 'Rivers']

    for sel, temp_table in zip(selections, temp_tables):
        cu.multi_msg("Creating temporary table called {0} for streams where {1}".format(temp_table, sel))
        LineDensity.line_density(zones_fc, zone_field, streams_fc, temp_table, sel)
        new_fields = ['SUM_LengthM', 'Density_MperHA']
        for f in new_fields:
            cu.rename_field(temp_table, f, temp_table + '_' + f, True)

    # join em up and copy to final
    temp_tables.remove('Streams')
    for t in temp_tables:
        try:
            arcpy.JoinField_management('Streams', zone_field, t, zone_field)
        #sometimes there's no table if it was an empty selection
        except:
            empty_fields = [temp_table + '_' + f for f in new_fields]
            for ef in empty_fields:
                arcpy.AddField_management('Streams', ef, 'Double')
                arcpy.CalculateField_management('Streams', ef, '0', 'PYTHON')
            continue

    # remove all the extra zoneID fields, which have underscore in name
    drop_fields = [f.name for f in arcpy.ListFields('Streams', zone_field + '_*')]
    for f in drop_fields:
        arcpy.DeleteField_management('Streams', f)
    arcpy.CopyRows_management('Streams', output_table)

    # clean up
    for item in ['Streams', 'no_coastlines'] + temp_tables:
        try:
            arcpy.Delete_management(item)
        except:
            continue


def main():
    zones_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    streams_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    streams_in_zones(zones_fc, zone_field, streams_fc, output_table)

def test():
    test_gdb = '../TestData_0411.gdb'
    zones_fc = os.path.join(test_gdb, 'HU12')
    zone_field = 'ZoneID'
    streams_fc =  os.path.join(test_gdb, 'Streams')
    output_table = 'C:/GISData/Scratch/Scratch.gdb/test_streams_in_zones'
    streams_in_zones(zones_fc, zone_field, streams_fc, output_table)

if __name__ == '__main__':
    main()
