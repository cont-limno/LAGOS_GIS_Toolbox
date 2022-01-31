import os

import arcpy
from arcpy import analysis as AN, management as DM


def calc(fc, glacial_extent_fc, zone_field, zone_name=''):
    # tab area
    if zone_name:
        zone_name = zone_name
    else:
        zone_name = os.path.basename(fc)
    g_field = '{}_glaciatedlatewisc_pct'.format(zone_name)
    AN.TabulateIntersection(fc, zone_field, glacial_extent_fc, 'in_memory/glacial_tab')
    glacial_pct = {r[0]:r[1] for r in arcpy.da.SearchCursor('in_memory/glacial_tab', [zone_field, 'PERCENTAGE'])}
    DM.AddField(fc, g_field, 'DOUBLE')
    with arcpy.da.UpdateCursor(fc, [zone_field, g_field]) as u_cursor:
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
    DM.Delete('in_memory/glacial_tab')