# filename: line_density_in_zones.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)

import os
import arcpy
import lagosGIS
from datetime import datetime as dt


def calc(zones_fc, zone_field, lines_fc, out_table, where_clause='', rename_label=''):
    """
    Calculates areal density of line features such as streams and roads.
    :param zones_fc: Zones feature class
    :param zone_field: Unique identifier for each zone
    :param lines_fc: The polyline feature class to be summarized for each zone
    :param out_table: Output table to save the result
    :param where_clause: (Optional) Query (SQL where clause) to filter polyline feature class before summary
    :param rename_label: (Optional) Text string to use as prefix for all output columns
    :return: None
    """

    # Setup: enforce coordinates, make names, filter lines if elected
    arcpy.env.workspace = 'in_memory'
    arcpy.env.outputCoordinatesystem = arcpy.SpatialReference(102039)
    if rename_label:
        out_density_field = '{}_mperha'.format(rename_label)
    else:
        out_density_field = '{}_mperha'.format(os.path.basename(lines_fc))

    if where_clause:
        lines_prep = arcpy.Select_analysis(lines_fc, 'lines_prep', where_clause)
    else:
        lines_prep = lines_fc

    # Perform identity analysis to join fields and crack lines at polygon boundaries
    arcpy.AddMessage("Cracking lines... {}".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines_identity = arcpy.Identity_analysis(lines_prep, zones_fc, 'lines_identity')
    arcpy.AddMessage("Summarizing results... {}".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    arcpy.AddField_management(lines_identity, 'length_m', 'DOUBLE')
    with arcpy.da.UpdateCursor(lines_identity, ['length_m', 'SHAPE@LENGTH']) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)

    # Calculate total length grouped by zone (numerator)
    lines_stat = arcpy.Statistics_analysis(lines_identity, 'lines_stat', 'length_m SUM', zone_field)
    lines_stat_full = lagosGIS.one_in_one_out(lines_stat, zones_fc, zone_field, 'lines_stat_full')

    # Get area of zones for density calculation (denominator))
    zones_area = {}
    with arcpy.da.SearchCursor(zones_fc, [zone_field, 'SHAPE@']) as cursor:
        for row in cursor:
            zones_area[row[0]] = row[1].getArea(units='HECTARES')

    # Calculate the density by dividing the numerator and denominator calculated and assign 0 if no lines were found
    # in the zone
    arcpy.AddField_management(lines_stat_full, out_density_field, 'DOUBLE')
    with arcpy.da.UpdateCursor(lines_stat_full, [zone_field, out_density_field, 'SUM_length_m']) as cursor:
        for row in cursor:
            zid, mperha, msum = row
            if msum is None:
                msum = 0  # replace NULL values with 0 which is physically accurate here
            if zid:
                mperha = msum/zones_area[zid]
                row = (zid, mperha, msum)
                cursor.updateRow(row)
            # this branch deletes ONE table row that has no zone id--total length of lines not in zones
            else:
                cursor.deleteRow()

    # Clean up
    arcpy.DeleteField_management(lines_stat_full, 'SUM_length_m')
    arcpy.DeleteField_management(lines_stat_full, 'FREQUENCY')
    arcpy.CopyRows_management(lines_stat_full, out_table)
    for item in ['lines_prep', lines_identity, lines_stat, lines_stat_full]:
        arcpy.Delete_management(item)


def main():
    # Parameters
    zones_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    lines_fc = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    where_clause = arcpy.GetParameterAsText(4)
    rename_label = arcpy.GetParameterAsText(5)
    calc(zones_fc, zone_field, lines_fc, out_table, where_clause, rename_label)


if __name__ == '__main__':
    main()

