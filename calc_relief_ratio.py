import os
import arcpy

def calc_relief_ratio(elevation_stats_table):
    zone_prefix = os.path.basename(elevation_stats_table).split('_')[0]
    elev_mean = arcpy.ListFields(elevation_stats_table, '*elevation_mean*')[0].name
    elev_min = arcpy.ListFields(elevation_stats_table, '*elevation_min*')[0].name
    elev_max = arcpy.ListFields(elevation_stats_table, '*elevation_max*')[0].name
    ratio = '{}_reliefratio'.format(zone_prefix)
    # arcpy.AddField_management(elevation_stats_table, ratio, 'DOUBLE')
    with arcpy.da.UpdateCursor(elevation_stats_table, [ratio, elev_mean, elev_min, elev_max]) as cursor:
        for row in cursor:
            ratio, mean, min, max = row
            if mean and min != max:
                ratio = (mean-min)/(max-min)
                row = [ratio, mean, min, max]
                cursor.updateRow(row)