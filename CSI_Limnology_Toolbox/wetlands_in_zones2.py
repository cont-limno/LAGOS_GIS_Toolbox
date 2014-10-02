# Wetlands in Zones, the new one
# this does all the wetland stuff at once for a given extent
import os
import arcpy
import polygons_in_zones
import csiutils as cu

def wetlands_in_zones(zones_fc, zone_field, wetlands_fc, output_table, dissolve_wetlands = True):

    # make sure we're only using the right types of wetlands, our feature
    # class excludes everything else but this is a guarantee this will
    # get checked at some point
    arcpy.env.workspace = 'in_memory'
    need_selection = False
    with arcpy.da.SearchCursor(wetlands_fc, ["ATTRIBUTE", "WETLAND_TYPE"]) as cursor:
        while need_selection is False:
            for row in cursor:
                if row[0][0] <> 'P':
                    need_selection = True
                if row[1] <> 'Freshwater Pond':
                    need_selection = True
    if need_selection:
        main_expr = """"ATTRIBUTE" LIKE 'P%'AND "WETLAND_TYPE" <> 'Freshwater_Pond'"""
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
    temp_tables = ['AllWetlandsUndissolved',
                'IsolatedWetlandsUndissolved',
                'SingleWetlandsUndissolved',
                'ConnectedWetlandsUndissolved',
                'ForestedWetlandsUndissolved',
                'ScrubShrubWetlandsUndissolved',
                'OpenWaterWetlandsUndissolved']

    for sel, temp_table in zip(selections, temp_tables):
        if sel:
            print("Creating temporary table for wetlands where {0}".format(sel))
            selected_wetlands = 'selected_wetlands'
            arcpy.Select_analysis(wetlands_fc, selected_wetlands, sel)
        else:
            print("Creating temporary table for all wetlands")
            selected_wetlands = wetlands_fc
        polygons_in_zones.polygons_in_zones(zones_fc, zone_field, selected_wetlands, temp_table, '')
        new_fields = ['Poly_Overlapping_AREA_ha', 'Poly_Contributing_AREA_ha', 'Poly_Overlapping_AREA_pct', 'Poly_Count']
        avg_size_field = temp_table + '_AvgSize_ha'
        arcpy.AddField_management(temp_table, avg_size_field , 'DOUBLE')
        arcpy.CalculateField_management(temp_table, avg_size_field, '!Poly_Contributing_AREA_ha!/!Poly_Count!', 'PYTHON')
        for f in new_fields:
            cu.rename_field(temp_table, f, f.replace('Poly', temp_table), True)

        if dissolve_wetlands == True:
            arcpy.Dissolve_management(selected_wetlands, 'dissolved_wetlands', multi_part = 'SINGLE_PART')
            dissolved_temp_table = temp_table.replace('Undissolved', 'Dissolved')
            temp_tables.append(dissolved_temp_table)
            polygons_in_zones.polygons_in_zones(zones_fc, zone_field, 'dissolved_wetlands', dissolved_temp_table, '')
            new_fields = ['Poly_Overlapping_AREA_ha', 'Poly_Contributing_AREA_ha', 'Poly_Overlapping_AREA_pct', 'Poly_Count']
            avg_size_field = dissolved_temp_table + '_AvgSize_ha'
            arcpy.AddField_management(dissolved_temp_table, avg_size_field , 'DOUBLE')
            arcpy.CalculateField_management(dissolved_temp_table, avg_size_field, '!Poly_Contributing_AREA_ha!/!Poly_Count!', 'PYTHON')
            for f in new_fields:
                cu.rename_field(dissolved_temp_table, f, f.replace('Poly', dissolved_temp_table), True)

    # join em up and copy to final
    temp_tables.remove('AllWetlandsUndissolved')
    for t in temp_tables:
        try:
            arcpy.JoinField_management('AllWetlandsUndissolved', zone_field, t, zone_field)
        # sometimes there's no table if it was an empty selection
        except:
            empty_fields = [f.replace('Poly', t) for f in new_fields]
            for ef in empty_fields:
                arcpy.AddField_management('AllWetlandsUndissolved', ef, 'Double')
                arcpy.CalculateField_management('AllWetlandsUndissolved', ef, '0', 'PYTHON')
            continue
    # remove all the extra zoneID fields, which have underscore in name
    drop_fields = [f.name for f in arcpy.ListFields('AllWetlandsUndissolved', zone_field + "_*")]
    for f in drop_fields:
        arcpy.DeleteField_management('AllWetlandsUndissolved', f)
    arcpy.CopyRows_management('AllWetlandsUndissolved', output_table)

    for item in ['AllWetlandsUndissolved', 'wetlands_fc_checked', 'dissolved_wetlands'] + temp_tables:
        try:
            arcpy.Delete_management(item)
        except:
            continue
    arcpy.ResetEnvironments()

def main():
    zones_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    wetlands_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    dissolve_wetlands = arcpy.GetParameter(4) # boolean
    wetlands_in_zones(zones_fc, zone_field, wetlands_fc, output_table, dissolve_wetlands)

def test():
    ws = 'C:/Users/smithn78/CSI_Processing/CSI/TestData_0411.gdb'
    zones_fc = os.path.join(ws, 'HU12')
    zone_field = 'ZoneID'
    wetlands_fc =  os.path.join(ws, 'Wetlands')
    output_table = 'C:/GISData/Scratch/Scratch.gdb/WETZONE_SEPT'
    dissolve_wetlands = True
    wetlands_in_zones(zones_fc, zone_field, wetlands_fc, output_table, dissolve_wetlands)

if __name__ == '__main__':
    main()
