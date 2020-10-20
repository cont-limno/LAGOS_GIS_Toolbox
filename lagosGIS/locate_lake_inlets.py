# filename: locate_lake_inlets.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): CONN
# tool type: re-usable (not in ArcGIS Toolbox)

import arcpy

import NHDNetwork
import lagosGIS

# this tool has a companion with symmetrical code: locate_lake_outlets.
def locate_lake_inlets(nhd_gdb, output_fc):
    """
    Creates a point feature class with inlet locations for LAGOS lakes within GDB, based on network connectivity.
    :param nhd_gdb: NHD-HR geodatabase you want to identify inlets for
    :param output_fc: Feature class to save the inlet points to
    :return:
    """

    arcpy.env.workspace = 'in_memory'
    network = NHDNetwork.NHDNetwork(nhd_gdb)
    network.define_lakes(force_lagos=True)

    # get lake outlet flowline IDs
    inlet_flowline_ids = network.identify_all_lakes_inlets()

    # convert end point of outlet flowlines to point representing outlet
    flowline_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id) for id in inlet_flowline_ids]))
    inlet_flowlines = arcpy.Select_analysis(network.flowline, 'inlet_flowlines', flowline_query)
    inlet_points = arcpy.FeatureVerticesToPoints_management(inlet_flowlines, 'inlet_points', 'START')
    output_fc = lagosGIS.select_fields(inlet_points, output_fc, ['Permanent_Identifier'])

    # add waterbody Perm ID
    network.map_flowlines_to_waterbodies()
    arcpy.AddField_management(output_fc, 'WBArea_Permanent_Identifier', 'TEXT', field_length=40)
    with arcpy.da.UpdateCursor(output_fc, ['Permanent_Identifier', 'WBArea_Permanent_Identifier']) as cursor:
        for row in cursor:
            row[1] = network.flowline_waterbody[row[0]]
            cursor.updateRow(row)

    # cleanup
    for item in [inlet_flowlines, inlet_points]:
        arcpy.Delete_management(item)

    return(output_fc)

