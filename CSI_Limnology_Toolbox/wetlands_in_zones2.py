# Wetlands in Zones, the new one
# this does all the wetland stuff at once for a given extent
import os
import arcpy
import polygons_in_zones
import csiutils as cu

def wetlands_in_zones(zones_fc, zone_field, wetlands_fc, output_table):

    # make sure we're only using the right types of wetlands, our feature
    # class excludes everything else but this is a guarantee this will
    # get checked at some point
    arcpy.env.workspace = 'in_memory'
    need_selection = False
    with arcpy.da.SearchCursor(wetlands_fc, ["ATTRIBUTE", "WETLAND_TY"]) as cursor:
        while need_selection is False:
            for row in cursor:
                if row[0][0] <> 'P':
                    need_selection = True
                if row[1] <> 'Freshwater Pond':
                    need_selection = True
    if need_selection:
        main_expr = """"ATTRIBUTE" LIKE 'P%'AND "WETLAND_TY" <> 'Freshwater_Pond'"""
        arcpy.Select_analysis(wetlands_fc, "wetlands_fc_checked", main_expr)
        wetlands_fc = os.path.join(arcpy.env.workspace, "wetlands_fc_checked")

    selections = ['',
                """"WetOrder" = 'Isolated'""",
                """"WetOrder" = 'Single'""",
                """"WetOrder" = 'Connected'""",
                """"VegType" = 'PFO'""",
                """"VegType" = 'PSS'""",
                """"VegType" = 'PEMorPAB'""",
                ]
    temp_tables = ['WL',
                'WL_Isolated',
                'WL_Single',
                'WL_Connected',
                'WL_PFO',
                'WL_PSS',
                'WL_PEMorPAB']

    for sel, temp_table in zip(selections, temp_tables):
        print("Creating temporary table for wetlands where {0}".format(sel))
        polygons_in_zones.polygons_in_zones(zones_fc, zone_field, wetlands_fc, temp_table, sel)
        new_fields = ['Poly_AREA_ha', 'Poly_AREA_pct', 'Poly_Count']
        for f in new_fields:
            cu.rename_field(temp_table, f, f.replace('Poly', temp_table), True)

    # join em up and copy to final
    temp_tables.remove('WL')
    for t in temp_tables:
        try:
            arcpy.JoinField_management('WL', zone_field, t, zone_field)
        # sometimes there's no table if it was an empty selection
        except:
            empty_fields = [f.replace('Poly', t) for r in new_fields]
            for ef in empty_fields:
                arcpy.AddField_management('WL', ef, 'Double')
                arcpy.CalculateField_management('WL', ef, '0', 'PYTHON')
            continue
    # remove all the extra zoneID fields, which have underscore in name
    drop_fields = [f.name for f in arcpy.ListFields('WL', 'ZoneID_*')]
    for f in drop_fields:
        arcpy.DeleteField_management('WL', f)
    arcpy.CopyRows_management('WL', output_table)

    for item in ['WL', 'wetlands_fc_checked'] + temp_tables:
        arcpy.Delete_management(item)

def main():
    zones_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    wetlands_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    wetlands_in_zones(zones_fc, zone_field, wetlands_fc, output_table)

def test():
    ws = 'C:/Users/smithn78/CSI_Processing/CSI/TestData_0411.gdb'
    zones_fc = os.path.join(ws, 'HU12')
    zone_field = 'ZoneID'
    wetlands_fc =  os.path.join(ws, 'Wetlands')
    output_table = 'C:/GISData/Scratch/Scratch.gdb/test_wetlands_in_zones'
    wetlands_in_zones(zones_fc, zone_field, wetlands_fc, output_table)

if __name__ == '__main__':
    main()
