import os
import arcpy
import lagosGIS
from datetime import datetime as dt


def calc_density(zones_fc, zone_field, lines_fc, out_table, where_clause='', rename_label=''):
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

    # calc total length grouped by zone (numerator)
    print("Statistics {}".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines_stat = arcpy.Statistics_analysis(lines_identity, 'lines_stat', 'length_m SUM', zone_field)
    print("One in One out {}".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines_stat_full = lagosGIS.one_in_one_out(lines_stat, zones_fc, zone_field, 'lines_stat_full')

    # get area of zones for density calc (denominator)
    print("Zones Area {}".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    zones_area = {}
    with arcpy.da.SearchCursor(zones_fc, [zone_field, 'SHAPE@']) as cursor:
        for row in cursor:
            zones_area[row[0]] = row[1].getArea(units='HECTARES')

    # calc the density by dividing
    print("Calc Density {}".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    arcpy.AddField_management(lines_stat_full, out_density_field, 'DOUBLE')
    with arcpy.da.UpdateCursor(lines_stat_full, [zone_field, out_density_field, 'SUM_length_m']) as cursor:
        for row in cursor:
            zid, mperha, msum = row
            if msum is None:
                msum = 0 # replace NULL values with 0 which is physically accurate here
            if zid:
                mperha = msum/zones_area[zid]
                row = (zid, mperha, msum)
                cursor.updateRow(row)
            # this branch deletes ONE row that has no zone id--total length of lines not in zones
            else:
                cursor.deleteRow()

    # delete extra field and ensure all input zones have output row
    print("Cleanup {}".format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    arcpy.DeleteField_management(lines_stat_full, 'SUM_length_m')
    arcpy.DeleteField_management(lines_stat_full, 'FREQUENCY')

    arcpy.CopyRows_management(lines_stat_full, out_table)

    # cleanup
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
    calc_density(zones_fc, zone_field, lines_fc, out_table, where_clause, rename_label)



if __name__ == '__main__':
    main()

