import os
import arcpy

def calc_density(zones_fc, zone_field, lines_fc, out_table, where_clause='', rename_label=''):
    arcpy.env.workspace = 'in_memory'
    if rename_label:
        out_field = '{}_mperha'.format(rename_label)
    else:
        out_field = '{}_mperha'.format(os.path.basename(lines_fc))

    if where_clause:
        lines_prep = arcpy.Select_analysis(lines_fc, 'lines_prep', where_clause)
    else:
        lines_prep = lines_fc

    # Perform identity analysis to join fields and crack lines at polygon boundaries
    lines_identity = arcpy.Identity_analysis(lines_prep, zones_fc, 'lines_identity')
    arcpy.AddField_management(lines_identity, 'length_m', 'DOUBLE')
    arcpy.CalculateField_management(lines_identity, 'length_m', '!shape.length!', 'PYTHON')
    lines_stat = arcpy.Statistics_analysis(lines_identity, 'lines_stat', 'length_m SUM', zone_field)
    arcpy.AddField_management(lines_identity, out_field, 'DOUBLE')

    zones_area = {}
    with arcpy.da.SearchCursor(zones_fc, [zone_field, 'SHAPE@']) as cursor:
        for row in cursor:
            zones_area[row[0]] = row[1].getArea(units='HECTARES')

    with arcpy.da.UpdateCursor(lines_stat, [zone_field, out_field, '']) as cursor:
        for row in cursor:
            zid, mperha, msum = row
            mperha = msum/zones_area[zid]
            row = (zid, mperha, msum)
            cursor.updateRow(row)

    # need to apply one in and one out

    arcpy.CopyRows_management(lines_stat, out_table)