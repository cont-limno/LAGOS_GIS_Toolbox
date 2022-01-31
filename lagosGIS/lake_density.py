# Lakes in Zones, the new one
# this does all the lake stuff at once for a given extent
import os
import arcpy
import polygon_density_in_zones
import lagosGIS

# Since the ws & nws layers were left with the jagged "rasterization" lines, they sometimes overlap lakes outside
# their area with small slivers. This function pre-processes the watersheds layer to erase those small sliver overlaps
# so that the lake count is more accurate.
# This tool is pretty slow.

def trim_watershed_slivers(watersheds_fc, lakes_fc, output_fc):
    arcpy.Intersect_analysis([watersheds_fc, lakes_fc], output_fc)
    # want to drop any intersections < 10% of area of the lake, as long as it overlaps shed by 10%+, will count
    arcpy.Select_analysis(output_fc, 'in_memory/slivers', 'Shape_Area < (.1 * lake_waterarea_ha) * 10000')
    arcpy.Delete_management(output_fc) # used this as a temp fc so we could have Shape_Area calculated
    arcpy.Erase_analysis(watersheds_fc, 'in_memory/slivers', output_fc)
    return output_fc


def calc_all(zones_fc, zone_field, lakes_fc, output_table):

    # make sure we're only using the right types of lakes, our feature
    # class excludes everything else but this is a guarantee this will
    # get checked at some point
    arcpy.env.workspace = 'in_memory'
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)

    temp_lakes = 'temp_lakes'
    arcpy.CopyFeatures_management(lakes_fc, temp_lakes)

    hectares_field = arcpy.ListFields(lakes_fc, 'lake_waterarea_ha')
    if not hectares_field:
        arcpy.AddField_management(temp_lakes, 'lake_waterarea_ha', 'DOUBLE')
        arcpy.CalculateField_management(temp_lakes, 'lake_waterarea_ha', '!shape.area@hectares!', 'PYTHON')

    # this bit enforces the correct lake type/size restriction just in case
    # geodata doesn't have this filtered already
    need_selection = False
    fcodes = lagosGIS.LAGOS_FCODE_LIST

    with arcpy.da.SearchCursor(temp_lakes, ["FCode"]) as cursor:
            for row in cursor:
                if row[0] not in fcodes:
                    need_selection = True

    if need_selection:
        whereClause = '''"FCode" IN %s''' % (fcodes,)
        arcpy.Select_analysis(temp_lakes, "lakes_lagos", whereClause)
        temp_lakes = os.path.join(arcpy.env.workspace, "lakes_lagos")

    if 'ws' in zones_fc:
        zones_fc = trim_watershed_slivers(zones_fc, lakes_fc, 'sliverless_sheds')

    selections = [
            # all lake selections
            "",

            """"lake_connectivity_class" = 'Isolated'""",
            """"lake_connectivity_class" = 'Headwater'""",
            """"lake_connectivity_class" = 'Drainage'""",
            """"lake_connectivity_class" = 'DrainageLk'""",
            """"lake_connectivity_class" = 'Terminal'""",
            """"lake_connectivity_class" = 'TerminalLk'""",

            """"lake_connectivity_permanent" = 'Isolated'""",
            """"lake_connectivity_permanent" = 'Headwater'""",
            """"lake_connectivity_permanent" = 'Drainage'""",
            """"lake_connectivity_permanent" = 'DrainageLk'""",
            """"lake_connectivity_permanent" = 'Terminal'""",
            """"lake_connectivity_permanent" = 'TerminalLk'""",
            
            # 4 hectare selections
            """"lake_waterarea_ha" >= 4""",

            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_class" = 'Isolated'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_class" = 'Headwater'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_class" = 'Drainage'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_class" = 'DrainageLk'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_class" = 'Terminal'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_class" = 'TerminalLk'""",

            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_permanent" = 'Isolated'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_permanent" = 'Headwater'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_permanent" = 'Drainage'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_permanent" = 'DrainageLk'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_permanent" = 'Terminal'""",
            """"lake_waterarea_ha" >= 4 AND "lake_connectivity_permanent" = 'TerminalLk'""",

            # 10 hectare selections
            """"lake_waterarea_ha" >= 10""",
    
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_class" = 'Isolated'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_class" = 'Headwater'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_class" = 'Drainage'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_class" = 'DrainageLk'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_class" = 'Terminal'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_class" = 'TerminalLk'""",
    
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_permanent" = 'Isolated'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_permanent" = 'Headwater'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_permanent" = 'Drainage'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_permanent" = 'DrainageLk'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_permanent" = 'Terminal'""",
            """"lake_waterarea_ha" >= 10 AND "lake_connectivity_permanent" = 'TerminalLk'"""
                ]

    temp_tables = ['lakes1ha_all',

                'lakes1ha_isolated',
                'lakes1ha_headwater',
                'lakes1ha_drainage',
                'lakes1ha_drainagelk',
                'lakes1ha_terminal',
                'lakes1ha_terminallk',

                'lakes1ha_isolatedperm',
                'lakes1ha_headwaterperm',
                'lakes1ha_drainageperm',
                'lakes1ha_drainagelkperm',
                'lakes1ha_terminalperm',
                'lakes1ha_terminallkperm',

                'lakes4ha_all',

                'lakes4ha_isolated',
                'lakes4ha_headwater',
                'lakes4ha_drainage',
                'lakes4ha_drainagelk',
                'lakes4ha_terminal',
                'lakes4ha_terminallk',

                'lakes4ha_isolatedperm',
                'lakes4ha_headwaterperm',
                'lakes4ha_drainageperm',
                'lakes4ha_drainagelkperm',
                'lakes4ha_terminalperm',
                'lakes4ha_terminallkperm',

                'lakes10ha_all',

               'lakes10ha_isolated',
               'lakes10ha_headwater',
               'lakes10ha_drainage',
               'lakes10ha_drainagelk',
               'lakes10ha_terminal',
               'lakes10ha_terminallk',

               'lakes10ha_isolatedperm',
               'lakes10ha_headwaterperm',
               'lakes10ha_drainageperm',
               'lakes10ha_drainagelkperm',
               'lakes10ha_terminalperm',
               'lakes10ha_terminallkperm'
                ]

    for sel, temp_table in zip(selections, temp_tables):
        arcpy.AddMessage("Creating temporary table called {0} for lakes where {1}".format(temp_table, sel))
        polygon_density_in_zones.calc(zones_fc, zone_field, temp_lakes, temp_table, sel)
        new_fields = ['Poly_ha', 'Poly_pct', 'Poly_n', 'Poly_nperha']
        for f in new_fields:
            arcpy.AlterField_management(temp_table, f, f.replace('Poly', temp_table))

    # join em up and copy to final
    temp_tables.remove('lakes1ha_all')
    for t in temp_tables:
        try:
            arcpy.JoinField_management('lakes1ha_all', zone_field, t, zone_field)
        #sometimes there's no table if it was an empty selection
        except:
            empty_fields = [f.replace('Poly', t) for f in new_fields]
            for ef in empty_fields:
                arcpy.AddField_management('lakes1ha_all', ef, 'Double')
                arcpy.CalculateField_management('lakes1ha_all', ef, '0', 'PYTHON')
            continue

    # remove all the extra zoneID fields, which have underscore in name
    drop_fields = [f.name for f in arcpy.ListFields('lakes1ha_all') if 'zoneid_' in f.name or 'AREA' in f.name]
    for f in drop_fields:
        arcpy.DeleteField_management('lakes1ha_all', f)
    arcpy.CopyRows_management('lakes1ha_all', output_table)

    # clean up
    arcpy.Delete_management('in_memory')


def main():
    zones_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    lakes_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    calc_all(zones_fc, zone_field, lakes_fc, output_table)

if __name__ == '__main__':
    main()
