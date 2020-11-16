import os
import arcpy
import lagosGIS

def calc_density(zones_fc, zone_field, lines_fc, out_table, where_clause='', rename_label=''):
    arcpy.env.workspace = 'in_memory'
    if rename_label:
        out_density_field = '{}_mperha'.format(rename_label)
    else:
        out_density_field = '{}_mperha'.format(os.path.basename(lines_fc))

    if where_clause:
        lines_prep = arcpy.Select_analysis(lines_fc, 'lines_prep', where_clause)
    else:
        lines_prep = lines_fc

    # Perform identity analysis to join fields and crack lines at polygon boundaries
    lines_identity = arcpy.Identity_analysis(lines_prep, zones_fc, 'lines_identity')
    arcpy.AddField_management(lines_identity, 'length_m', 'DOUBLE')
    arcpy.CalculateField_management(lines_identity, 'length_m', '!shape.length!', 'PYTHON')

    # calc total length grouped by zone (numerator)
    lines_stat = arcpy.Statistics_analysis(lines_identity, 'lines_stat', 'length_m SUM', zone_field)
    arcpy.CopyRows_management(lines_stat, out_table)

    # get area of zones for density calc (denominator)
    zones_area = {}
    with arcpy.da.SearchCursor(zones_fc, [zone_field, 'SHAPE@']) as cursor:
        for row in cursor:
            zones_area[row[0]] = row[1].getArea(units='HECTARES')

    # calc the density by dividing
    arcpy.AddField_management(lines_stat, out_density_field, 'DOUBLE')
    with arcpy.da.UpdateCursor(lines_stat, [zone_field, out_density_field, 'SUM_length_m']) as cursor:
        for row in cursor:
            zid, mperha, msum = row
            if zid:
                mperha = msum/zones_area[zid]
                row = (zid, mperha, msum)
                cursor.updateRow(row)
            # this branch deletes ONE row that has no zone id--total length of lines not in zones
            else:
                cursor.deleteRow()

    # delete extra field and ensure all input zones have output row
    arcpy.DeleteField_management(lines_stat, 'SUM_length_m')
    arcpy.DeleteField_management(lines_stat, 'FREQUENCY')
    lagosGIS.one_in_one_out(lines_stat, zones_fc, zone_field, out_table)

    # cleanup
    for item in ['lines_prep', lines_identity, lines_stat]:
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

