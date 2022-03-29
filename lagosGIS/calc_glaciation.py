# filename: calc_glaciation.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS, GEO
# tool type: re-usable (NOT in ArcGIS Toolbox)

import os

import arcpy
from arcpy import analysis as AN, management as DM


def calc(zone_fc, glacial_extent_fc, zone_field, zone_prefix=''):
    """ Calculates the percentage of the zonal polygon that was covered by the polygon extent of the glaciation dataset.
    Modifies the original dataset.

    :param zone_fc: Polygon feature class containing the zones to be characterized. The input will be modified.
    :param glacial_extent_fc: Polygon feature class containing a single (multi-part permitted) polygon showing
    maximum glacial extent
    :param zone_field: Field name for the zone identifier
    :param zone_prefix: (Optional) Short name or tag to use as prefix for all output column names and the table name
    :return: The path to the modified zone polygon feature class
    """

    # Set-up names
    if zone_prefix:
        zone_prefix = zone_prefix
    else:
        zone_prefix = os.path.basename(zone_fc)
    g_field = '{}_glaciatedlatewisc_pct'.format(zone_prefix)

    # Tabulate area and rename output field
    AN.TabulateIntersection(zone_fc, zone_field, glacial_extent_fc, 'in_memory/glacial_tab')
    glacial_pct = {r[0]:r[1] for r in arcpy.da.SearchCursor('in_memory/glacial_tab', [zone_field, 'PERCENTAGE'])}
    DM.AddField(zone_fc, g_field, 'DOUBLE')

    # Cursor will essentially round to 2 decimal places, but also correct for TabulateArea percentages that slightly
    # exceed 100 for whatever reason
    with arcpy.da.UpdateCursor(zone_fc, [zone_field, g_field]) as u_cursor:
        for row in u_cursor:
            zoneid, glaciation = row
            if zoneid not in glacial_pct:
                glaciation = 0
            else:
                if glacial_pct[zoneid] >= 99.99:
                    glaciation = 100
                elif glacial_pct[zoneid] < 0.01:
                    glaciation = 0
                else:
                    glaciation = glacial_pct[zoneid]
            u_cursor.updateRow((zoneid, glaciation))

    # Clean up
    DM.Delete('in_memory/glacial_tab')

    return zone_fc