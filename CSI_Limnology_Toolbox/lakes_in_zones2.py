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

    # using in_memory workspace means no SHAPE@AREA attribute later so I
    # need to calculate another field with the area using temp on disk
    # then go ahead and copy to memory, delete temp
    temp_workspace = cu.create_temp_GDB('lakezone')
    temp_lakes = os.path.join(temp_workspace, 'temp_lakes')
    arcpy.CopyFeatures_management(lakes_fc, temp_lakes)
    arcpy.AddField_management(temp_lakes, 'Area_ha', 'DOUBLE')
    arcpy.CalculateField_management(temp_lakes, 'Area_ha', '!shape.area@hectares!', 'PYTHON')

    # this bit enforces the correct lake type/size restriction just in case
    # geodata doesn't have this filtered already
    need_selection = False
    fcodes = (39000, 39004, 39009, 39010, 39011, 39012,
                43600, 43613, 43615, 43617, 43618, 43619, 43621)
    with arcpy.da.SearchCursor(temp_lakes, ["FCode"]) as cursor:
            for row in cursor:
                if row[0] not in fcodes + (43061,):
                    need_selection = True

    if need_selection:
        whereClause = '''
                    "(AreaSqKm" >=0.04 AND "FCode" IN %s\
                    OR ("AreaSqKm" >= 0.1 AND "FCode" = 43601)''' % (fcodes,)
        arcpy.Select_analysis(temp_lakes, "lakes_4ha", main_expr)
        temp_lakes = os.path.join(arcpy.env.workspace, "lakes_4ha")


    selections = [""""Area_ha" >= 4""",
                """"Area_ha" >= 4 AND "Connection" = 'Isolated'""",
                """"Area_ha" >= 4 AND "Connection" = 'Headwater'""",
                """"Area_ha" >= 4 AND "Connection" = 'DR_Stream'""",
                """"Area_ha" >= 4 AND "Connection" = 'DR_LakeStream'""",
                """"Area_ha" >= 4 AND "Area_ha" < 10""",
                """"Area_ha" >= 4 AND "Area_ha" < 10 AND "Connection" = 'Isolated'""",
                """"Area_ha" >= 4 AND "Area_ha" < 10 AND "Connection" = 'Headwater'""",
                """"Area_ha" >= 4 AND "Area_ha" < 10 AND "Connection" = 'DR_Stream'""",
                """"Area_ha" >= 4 AND "Area_ha" < 10 AND "Connection" = 'DR_LakeStream'""",
                """"Area_ha" >= 10""",
                """"Area_ha" >= 10 AND "Connection" = 'Isolated'""",
                """"Area_ha" >= 10 AND "Connection" = 'Headwater'""",
                """"Area_ha" >= 10 AND "Connection" = 'DR_Stream'""",
                """"Area_ha" >= 10 AND "Connection" = 'DR_LakeStream'"""
                ]
    temp_tables = ['Lakes4ha',
                'Lakes4ha_Isolated',
                'Lakes4ha_Headwater',
                'Lakes4ha_DRStream',
                'Lakes4ha_DRLakeStream',
                'Lakes4to10ha',
                'Lakes4to10ha_Isolated',
                'Lakes4to10ha_Headwater',
                'Lakes4to10ha_DRStream',
                'Lakes4to10ha_DRLakeStream',
                'Lakes10ha',
                'Lakes10ha_Isolated',
                'Lakes10ha_Headwater',
                'Lakes10ha_DRStream',
                'Lakes10ha_DRLakeStream'
                ]

    for sel, temp_table in zip(selections, temp_tables):
        cu.multi_msg("Creating temporary table called {0} for lakes where {1}".format(temp_table, sel))
        polygons_in_zones.polygons_in_zones(zones_fc, zone_field, temp_lakes, temp_table, sel)
        new_fields = ['Poly_AREA_ha', 'Poly_AREA_pct', 'Poly_Count']
        for f in new_fields:
            cu.rename_field(temp_table, f, f.replace('Poly', temp_table), True)

    # join em up and copy to final
    temp_tables.remove('Lakes4ha')
    for t in temp_tables:
        try:
            arcpy.JoinField_management('Lakes4ha', zone_field, t, zone_field)
        #sometimes there's no table if it was an empty selection
        except:
            empty_fields = [f.replace('Poly', t) for f in new_fields]
            for ef in empty_fields:
                arcpy.AddField_management('Lakes4ha', ef, 'Double')
                arcpy.CalculateField_management('Lakes4ha', ef, '0', 'PYTHON')
            continue

    # remove all the extra zoneID fields, which have underscore in name
    drop_fields = [f.name for f in arcpy.ListFields('Lakes4ha', 'ZoneID_*')]
    for f in drop_fields:
        arcpy.DeleteField_management('Lakes4ha', f)
    arcpy.CopyRows_management('Lakes4ha', output_table)

    # clean up
    for item in ['Lakes4ha', temp_lakes, os.path.dirname(temp_workspace)] + temp_tables:
        arcpy.Delete_management(item)


def main():
    zones_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    lakes_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    lakes_in_zones(zones_fc, zone_field, lakes_fc, output_table)

def test():
    ws = 'C:/Users/smithn78/CSI_Processing/CSI/TestData_0411.gdb'
    zones_fc = os.path.join(ws, 'HU12')
    zone_field = 'ZoneID'
    lakes_fc =  os.path.join(ws, 'Lakes_1ha')
    output_table = 'C:/GISData/Scratch/Scratch.gdb/test_lakes_in_zones_updates'
    lakes_in_zones(zones_fc, zone_field, lakes_fc, output_table)

if __name__ == '__main__':
    main()
