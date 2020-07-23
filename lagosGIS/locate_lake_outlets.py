import os
import arcpy
import lagosGIS
import nhdplushr_tools as ntools

# this tool has a companion with symmetrical code: locate_lake_inlets.
def locate_lake_outlets(nhd_gdb, output_fc):
    """
    Creates a point feature class with outlet locations for LAGOS lakes within GDB, based on network connectivity.
    :param nhd_gdb: NHD-HR geodatabase you want to identify outlets for
    :param output_fc: Feature class to save the outlet points to
    :return:
    """
    arcpy.env.workspace = 'in_memory'
    network = ntools.NHDNetwork(nhd_gdb)
    network.define_lakes(force_lagos=True)

    # get lake outlet flowline IDs
    outlet_flowline_ids = network.identify_all_lakes_outlets()

    # convert end point of outlet flowlines to point representing outlet
    flowline_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id) for id in outlet_flowline_ids]))
    outlet_flowlines = arcpy.Select_analysis(network.flowline, 'outlet_flowlines', flowline_query)
    outlet_points = arcpy.FeatureVerticesToPoints_management(outlet_flowlines, 'outlet_points', 'END')
    output_fc = lagosGIS.select_fields(outlet_points, output_fc, ['Permanent_Identifier'])

    # add waterbody Perm ID
    network.map_flowlines_to_waterbodies()
    arcpy.AddField_management(output_fc, 'WBArea_Permanent_Identifier', 'TEXT', field_length=40)
    with arcpy.da.UpdateCursor(output_fc, ['Permanent_Identifier', 'WBArea_Permanent_Identifier']) as cursor:
        for row in cursor:
            row[1] = network.flowline_waterbody[row[0]]
            cursor.updateRow(row)

    # cleanup
    for item in [outlet_flowlines, outlet_points]:
        arcpy.Delete_management(item)

    return(output_fc)
