# filename: stream_density.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)

import os
import arcpy
import lagosGIS


def calc_all(zones_fc, zone_field, lines_fc, out_table, zone_prefix=''):
    arcpy.env.workspace = 'in_memory'
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    if zone_prefix:
        streams_density_field = '{}_streams_all_mperha'.format(zone_prefix)
        perm_density_field = '{}_streams_allperm_mperha'.format(zone_prefix)
        rivers_density_field = '{}_streams_rivers_mperha'.format(zone_prefix)
        midreaches_density_field = '{}_streams_midreaches_mperha'.format(zone_prefix)
        headwaters_density_field = '{}_streams_headwaters_mperha'.format(zone_prefix)
    else:
        streams_density_field = '{}_streams_all_mperha'.format(os.path.basename(zones_fc))
        perm_density_field = '{}_streams_allperm_mperha'.format(os.path.basename(zones_fc))
        rivers_density_field = '{}_streams_rivers_mperha'.format(os.path.basename(zones_fc))
        midreaches_density_field = '{}_streams_midreaches_mperha'.format(os.path.basename(zones_fc))
        headwaters_density_field = '{}_streams_headwaters_mperha'.format(os.path.basename(zones_fc))

    intermit_fcodes = ['46003', '46007']

    # Keep only necessary columns from zones
    zones_only = lagosGIS.select_fields(zones_fc, 'in_memory/zones_only', [zone_field], convert_to_table=False)

    # Perform identity analysis to join fields and crack lines at polygon boundaries
    arcpy.AddMessage("Cracking lines...")
    lines_identity = arcpy.Identity_analysis(lines_fc, zones_only, 'lines_identity', cluster_tolerance='1 meters')
    arcpy.AddMessage("Summarizing results...")
    print("Calculating length...")
    arcpy.AddField_management(lines_identity, 'length_m', 'DOUBLE')
    with arcpy.da.UpdateCursor(lines_identity, ['length_m', 'SHAPE@LENGTH']) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)

    # make permanent-only layer
    perm_query = 'FCode NOT IN ({})'.format(','.join(intermit_fcodes))
    lines_identity_perm = arcpy.Select_analysis(lines_identity, 'lines_identity_perm', perm_query)

    # make strahler grouped layers
    rivers_query = 'StreamOrder >= 7'
    midreaches_query = 'StreamOrder > 3 AND StreamOrder <= 6'
    headwaters_query = 'StreamOrder <= 3 OR StreamOrder IS NULL'
    lines_identity_rivers = arcpy.Select_analysis(lines_identity, 'lines_identity_rivers', rivers_query)
    lines_identity_midreaches = arcpy.Select_analysis(lines_identity, 'lines_identity_midreaches', midreaches_query)
    lines_identity_headwaters = arcpy.Select_analysis(lines_identity, 'lines_identity_headwaters', headwaters_query)



    def summarize_cracked(cracked_lines, density_field_name):
        # calc total length grouped by zone (numerator)
        print("Statistics...")
        lines_stat = arcpy.Statistics_analysis(cracked_lines, 'lines_stat', 'length_m SUM', zone_field)
        lines_stat_full = lagosGIS.one_in_one_out(lines_stat, zones_fc, zone_field, 'lines_stat_full')

        # get area of zones for density calc (denominator)
        print("Getting zone areas...")
        zones_area = {}
        with arcpy.da.SearchCursor(zones_fc, [zone_field, 'SHAPE@']) as cursor:
            for row in cursor:
                zones_area[row[0]] = row[1].getArea(units='HECTARES')

        # calc the density by dividing
        print("Calculating density...")
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
    rivers_summary = summarize_cracked(lines_identity_rivers, rivers_density_field)
    midreaches_summary = summarize_cracked(lines_identity_midreaches, midreaches_density_field)
    headwaters_summary = summarize_cracked(lines_identity_headwaters, headwaters_density_field)

    # put all tables together
    arcpy.AddField_management(streams_summary, perm_density_field, 'DOUBLE')
    arcpy.AddField_management(streams_summary, rivers_density_field, 'DOUBLE')
    arcpy.AddField_management(streams_summary, midreaches_density_field, 'DOUBLE')
    arcpy.AddField_management(streams_summary, headwaters_density_field, 'DOUBLE')
    perm_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(perm_summary, [zone_field, perm_density_field])}
    rivers_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(rivers_summary, [zone_field, rivers_density_field])}
    midreaches_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(midreaches_summary, [zone_field, midreaches_density_field])}
    headwaters_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(headwaters_summary, [zone_field, headwaters_density_field])}
    cursor_fields = [zone_field,
                     perm_density_field,
                     rivers_density_field,
                     midreaches_density_field,
                     headwaters_density_field]
    with arcpy.da.UpdateCursor(streams_summary, cursor_fields) as cursor:
        for row in cursor:
            row[1] = perm_dict[row[0]]
            row[2] = rivers_dict[row[0]]
            row[3] = midreaches_dict[row[0]]
            row[4] = headwaters_dict[row[0]]
            cursor.updateRow(row)

    # copy to final output
    arcpy.CopyRows_management(streams_summary, out_table)

    # cleanup
    for item in [lines_identity, lines_identity_perm, streams_summary, perm_summary, rivers_summary,
                 midreaches_summary, headwaters_summary]:
        arcpy.Delete_management(item)

def main():
    # Parameters
    zones_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    lines_fc = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    zone_prefix = arcpy.GetParameterAsText(4)
    calc_all(zones_fc, zone_field, lines_fc, out_table, zone_prefix)


if __name__ == '__main__':
    main()

