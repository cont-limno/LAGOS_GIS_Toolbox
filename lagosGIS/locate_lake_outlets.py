import os
import arcpy
import lagosGIS
import nhdplushr_tools as ntools

def locate_lake_outlets(nhd_gdb, output_fc):
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
    return(output_fc)

    # cleanup
    for item in [outlet_flowlines, outlet_points]:
        arcpy.Delete_management(item)