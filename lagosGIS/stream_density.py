import os
import arcpy
import lagosGIS


def calc_density(zones_fc, zone_field, lines_fc, out_table, zone_prefix=''):
    arcpy.env.workspace = 'in_memory'
    if zone_prefix:
        streams_density_field = '{}_streams_all_mperha'.format(os.path.basename(zone_prefix))
        perm_density_field = '{}_streams_allperm_mperha'.format(os.path.basename(zone_prefix))
    intermit_fcodes = ['46003', '46007']
    # TODO: Add projection check

    # Perform identity analysis to join fields and crack lines at polygon boundaries
    arcpy.AddMessage("Cracking lines...")
    lines_identity = arcpy.Identity_analysis(lines_fc, zones_fc, 'lines_identity')
    arcpy.AddMessage("Summarizing results...")
    arcpy.AddField_management(lines_identity, 'length_m', 'DOUBLE')
    arcpy.CalculateField_management(lines_identity, 'length_m', '!shape.length!', 'PYTHON')

    # make permanent-only layer
    perm_query = 'FCode NOT IN ({})'.format(','.join(intermit_fcodes))
    lines_identity_perm = arcpy.Select_analysis(lines_identity, 'lines_identity_perm', perm_query)

    def summarize_cracked(cracked_lines, density_field_name):
        # calc total length grouped by zone (numerator)
        lines_stat = arcpy.Statistics_analysis(cracked_lines, 'lines_stat', 'length_m SUM', zone_field)
        lines_stat_full = lagosGIS.one_in_one_out(lines_stat, zones_fc, zone_field, 'lines_stat_full')

        # get area of zones for density calc (denominator)
        zones_area = {}
        with arcpy.da.SearchCursor(zones_fc, [zone_field, 'SHAPE@']) as cursor:
            for row in cursor:
                zones_area[row[0]] = row[1].getArea(units='HECTARES')

        # calc the density by dividing
        arcpy.AddField_management(lines_stat_full, density_field_name, 'DOUBLE')
        with arcpy.da.UpdateCursor(lines_stat_full, [zone_field, density_field_name, 'SUM_length_m']) as cursor:
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
        arcpy.DeleteField_management(lines_stat_full, 'SUM_length_m')
        arcpy.DeleteField_management(lines_stat_full, 'FREQUENCY')

        # copy output to an in_memory fc with same name as output field so we can delete lines_stat_full
        summarized = arcpy.CopyRows_management(lines_stat_full, density_field_name)
        # cleanup
        for item in [lines_stat, lines_stat_full]:
            arcpy.Delete_management(item)

        return summarized

    # run summaries
    streams_summary = summarize_cracked(lines_identity, streams_density_field)
    perm_summary = summarize_cracked(lines_identity_perm, perm_density_field)

    # put both tables together
    arcpy.AddField_management(streams_summary, perm_density_field, 'DOUBLE')
    join_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(perm_summary, [zone_field, perm_density_field])}
    with arcpy.da.UpdateCursor(streams_summary, [zone_field, perm_density_field]) as cursor:
        for row in cursor:
            row[1] = join_dict[row[0]]
            cursor.updateRow(row)

    # copy to final output
    arcpy.CopyRows_management(streams_summary, out_table)

    # cleanup
    for item in [lines_identity, lines_identity_perm, streams_summary, perm_summary]:
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

