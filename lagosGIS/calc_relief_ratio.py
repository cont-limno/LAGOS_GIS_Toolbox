# filename: calc_relief_ratio.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (NOT in ArcGIS Toolbox)

import os
import arcpy


def calc_relief_ratio(elevation_stats_table):
    """
    Calculates watershed relief ratio using the mean, minimum, and maximum elevation for the zone polygon that was
    calculated with Zonal Summary of Raster Data.
    :param elevation_stats_table: Output table from Zonal Summary of Raster Data tool containing minimum, maximum,
    mean elevation for each zone
    :return: elevation_stats_table
    """

    # Find and add fields
    zone_prefix = os.path.basename(elevation_stats_table).split('_')[0]
    elev_mean = arcpy.ListFields(elevation_stats_table, '*elevation_mean*')[0].name
    elev_min = arcpy.ListFields(elevation_stats_table, '*elevation_min*')[0].name
    elev_max = arcpy.ListFields(elevation_stats_table, '*elevation_max*')[0].name
    ratio = '{}_reliefratio'.format(zone_prefix)
    arcpy.AddField_management(elevation_stats_table, ratio, 'DOUBLE')

    # Calculate the "elevation relief ratio"
    with arcpy.da.UpdateCursor(elevation_stats_table, [ratio, elev_mean, elev_min, elev_max]) as cursor:
        for row in cursor:
            ratio, mean, min, max = row
            if mean and min != max:
                ratio = (mean-min)/(max-min)
                row = [ratio, mean, min, max]
                cursor.updateRow(row)

    return elevation_stats_table