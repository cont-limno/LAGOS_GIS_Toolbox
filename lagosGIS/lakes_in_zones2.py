# Lakes in Zones, the new one
# this does all the lake stuff at once for a given extent
import os
import arcpy
import polygons_in_zones
import csiutils as cu

def lakes_in_zones(zones_fc, zone_field, lakes_fc, output_table):

    # make sure we're only using the right types of lakes, our feature
    # class excludes everything else but this is a guarantee this will
    # get checked at some point
    arcpy.env.workspace = 'in_memory'

    temp_lakes = 'temp_lakes'
    arcpy.CopyFeatures_management(lakes_fc, temp_lakes)

    hectares_field = arcpy.ListFields(lakes_fc, 'Hectares')
    if not hectares_field:
        arcpy.AddField_management(temp_lakes, 'Hectares', 'DOUBLE')
        arcpy.CalculateField_management(temp_lakes, 'Hectares', '!shape.area@hectares!', 'PYTHON')

    # this bit enforces the correct lake type/size restriction just in case
    # geodata doesn't have this filtered already
    need_selection = False
    fcodes = (39000, 39004, 39009, 39010, 39011, 39012,
                43600, 43613, 43615, 43617, 43618, 43619, 43621)

    with arcpy.da.SearchCursor(temp_lakes, ["FCode"]) as cursor:
            for row in cursor:
                if row[0] not in fcodes:
                    need_selection = True

    if need_selection:
        whereClause = '''
                    ("Hectares" >= 4 AND "FCode" IN %s)''' % (fcodes,)
        arcpy.Select_analysis(temp_lakes, "lakes_4ha", whereClause)
        temp_lakes = os.path.join(arcpy.env.workspace, "lakes_4ha")


    selections = [
            # all lake selections
            "",

            """"Connectivity_Class" = 'Isolated'""",
            """"Connectivity_Class" = 'Headwater'""",
            """"Connectivity_Class" = 'Drainage'""",
            """"Connectivity_Class" = 'DrainageLk'""",

            """"Connectivity_Permanent" = 'Isolated'""",
            """"Connectivity_Permanent" = 'Headwater'""",
            """"Connectivity_Permanent" = 'Drainage'""",
            """"Connectivity_Permanent" = 'DrainageLk'""",
            
            # 4 hectare selections
            """"Hectares" >= 4""",

            """"Hectares" >= 4 AND "Connectivity_Class" = 'Isolated'""",
            """"Hectares" >= 4 AND "Connectivity_Class" = 'Headwater'""",
            """"Hectares" >= 4 AND "Connectivity_Class" = 'Drainage'""",
            """"Hectares" >= 4 AND "Connectivity_Class" = 'DrainageLk'""",

            """"Hectares" >= 4 AND "Connectivity_Permanent" = 'Isolated'""",
            """"Hectares" >= 4 AND "Connectivity_Permanent" = 'Headwater'""",
            """"Hectares" >= 4 AND "Connectivity_Permanent" = 'Drainage'""",
            """"Hectares" >= 4 AND "Connectivity_Permanent" = 'DrainageLk'"""
                ]

    temp_tables = ['Lakes1ha_All',

                'Lakes1ha_Isolated',
                'Lakes1ha_Headwater',
                'Lakes1ha_Drainage',
                'Lakes1ha_DrainageLk',

                'Lakes1ha_IsolatedPerm',
                'Lakes1ha_HeadwaterPerm',
                'Lakes1ha_DrainagePerm',
                'Lakes1ha_DrainageLkPerm',

                'Lakes4ha_All',

                'Lakes4ha_Isolated',
                'Lakes4ha_Headwater',
                'Lakes4ha_Drainage',
                'Lakes4ha_DrainageLk',

                'Lakes4ha_IsolatedPerm',
                'Lakes4ha_HeadwaterPerm',
                'Lakes4ha_DrainagePerm',
                'Lakes4ha_DrainageLkPerm'
                ]

    for sel, temp_table in zip(selections, temp_tables):
        arcpy.AddMessage("Creating temporary table called {0} for lakes where {1}".format(temp_table, sel))
        polygons_in_zones.polygons_in_zones(zones_fc, zone_field, temp_lakes, temp_table, sel)
        new_fields = ['Poly_Ha', 'Poly_Pct', 'Poly_n', 'Poly_nperha']
        for f in new_fields:
            arcpy.AlterField_management(temp_table, f, f.replace('Poly', temp_table))

    # join em up and copy to final
    temp_tables.remove('Lakes1ha_All')
    for t in temp_tables:
        try:
            arcpy.JoinField_management('Lakes1ha_All', zone_field, t, zone_field)
        #sometimes there's no table if it was an empty selection
        except:
            empty_fields = [f.replace('Poly', t) for f in new_fields]
            for ef in empty_fields:
                arcpy.AddField_management('Lakes1ha_All', ef, 'Double')
                arcpy.CalculateField_management('Lakes1ha_All', ef, '0', 'PYTHON')
            continue

    # remove all the extra zoneID fields, which have underscore in name
    drop_fields = [f.name for f in arcpy.ListFields('Lakes1ha_All', 'ZoneID_*')]
    for f in drop_fields:
        arcpy.DeleteField_management('Lakes1ha_All', f)
    arcpy.CopyRows_management('Lakes1ha_All', output_table)

    # clean up
    arcpy.Delete_management('in_memory')


def main():
    zones_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    lakes_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    lakes_in_zones(zones_fc, zone_field, lakes_fc, output_table)

if __name__ == '__main__':
    main()
