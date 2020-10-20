# filename: upstream_lakes.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import os
import arcpy

import NHDNetwork


def count(nhd_gdb, output_table):
    """
    This tool calculates the number and area of upstream lakes for each focal lake in the input data. The results are
    calculated for 3 size classes: all lakes (lakes1ha), lakes >= 4ha, and lakes >= 10ha. Network analysis is used
    to search upstream and is limited to the area included in the input NHD GDB. This tool relies on
    NHDNetwork.find_upstream_lakes to do the calculations.
    This tool will generate the following fields in a new table, using the lagoslakeid as the main identifier:
    lake_lakes1ha_upstream_n:   count of lakes greater than or equal to 1 ha upstream of the focal lake, connected via
                                surface streams
    lake_lakes1ha_upstream_ha:  total area of lakes greater than or equal to 1 ha upstream of the focal lake, connected
                                via surface streams
    lake_lakes4ha_upstream_n:   count of lakes greater than or equal to 4 ha upstream of the focal lake, connected via
                                surface streams
    lake_lakes4ha_upstream_ha:  total area of lakes greater than or equal to 4 ha upstream of the focal lake, connected
                                via surface streams
    lake_lakes10ha_upstream_n:  count of lakes greater than or equal to 10 ha upstream of the focal lake, connected via
                                surface streams
    lake_lakes10ha_upstream_ha: total area of lakes greater than or equal to 10 ha upstream of the focal lake, connected
                                via surface streams

    :param nhd_gdb: The file path for a high-resolution NHD or NHDPlus geodatabase for a single subregion/HU4.
    :param output_table: The path to save the output table to (suggested: FileGDB table)
    :return: The output table path
    """
    nhd_network = NHDNetwork.NHDNetwork(nhd_gdb)

    nhd_network.define_lakes(strict_minsize=False, force_lagos=True)
    waterbody_ids = nhd_network.lakes_areas.keys()
    nhd_network.define_lakes(strict_minsize=False, force_lagos=False)

    arcpy.AddMessage("Counting all lakes...")

    # all lakes count, see NHDNetwork script for more details
    upstream_data = {}
    for wb_id in waterbody_ids:
        uplakes = nhd_network.find_upstream_lakes(wb_id, 'list', area_threshold=0.01)
        uplakes_areas = [nhd_network.lakes_areas[id] for id in uplakes]
        uplakes_1ha = filter(lambda a: a >= 0.01, uplakes_areas)
        uplakes_4ha = filter(lambda a: a >= 0.04, uplakes_areas)
        uplakes_10ha = filter(lambda a: a >= 0.1, uplakes_areas)
        count_1ha = len(uplakes_1ha)
        area_1ha = sum(uplakes_1ha) * 100 # convert to hectares
        count_4ha = len(uplakes_4ha)
        area_4ha = sum(uplakes_4ha) * 100 # convert to hectares
        count_10ha = len(uplakes_10ha)
        area_10ha = sum(uplakes_10ha) * 100 # convert to hectares
        upstream_data[wb_id] = [count_1ha, area_1ha, count_4ha, area_4ha, count_10ha, area_10ha]

    # make an output table
    arcpy.AddMessage("Saving output...")
    output = arcpy.CreateTable_management(os.path.dirname(output_table), os.path.basename(output_table))
    arcpy.AddField_management(output, 'lake_lakes1ha_upstream_n', 'LONG')
    arcpy.AddField_management(output, 'lake_lakes1ha_upstream_ha', 'DOUBLE')
    arcpy.AddField_management(output, 'lake_lakes4ha_upstream_n', 'LONG')
    arcpy.AddField_management(output, 'lake_lakes4ha_upstream_ha', 'DOUBLE')
    arcpy.AddField_management(output, 'lake_lakes10ha_upstream_n', 'LONG')
    arcpy.AddField_management(output, 'lake_lakes10ha_upstream_ha', 'DOUBLE')

    # this matches order of upstream_data elements, above
    insert_fields = ['lake_lakes1ha_upstream_n',
                     'lake_lakes1ha_upstream_ha',
                     'lake_lakes4ha_upstream_n',
                     'lake_lakes4ha_upstream_ha',
                     'lake_lakes10ha_upstream_n',
                     'lake_lakes10ha_upstream_ha',
                     ]

    # get all the ids
    arcpy.AddField_management(output, 'Permanent_Identifier', 'TEXT', field_length=40)
    write_id_names = ['Permanent_Identifier']
    if arcpy.ListFields(nhd_network.waterbody, 'lagoslakeid'):
        write_id_names.append('lagoslakeid')
        arcpy.AddField_management(output, 'lagoslakeid', 'LONG')
    if arcpy.ListFields(nhd_network.waterbody, 'nhd_merge_id'):
        write_id_names.append('nhd_merge_id')
        arcpy.AddField_management(output, 'nhd_merge_id', 'TEXT', field_length=100)

    write_id_map = {r[0]: list(r)
                    for r in arcpy.da.SearchCursor(nhd_network.waterbody, write_id_names)}

    # write the table
    cursor_fields = write_id_names + insert_fields
    rows = arcpy.da.InsertCursor(output, cursor_fields)
    for id in waterbody_ids:
        write_ids = write_id_map[id]
        row = write_ids + upstream_data[id]
        rows.insertRow(row)


def main():
    nhd_gdb = arcpy.GetParameterAsText(0)
    output_table = arcpy.GetParameterAsText(1)

    count(nhd_gdb, output_table)


if __name__ == '__main__':
    main()




