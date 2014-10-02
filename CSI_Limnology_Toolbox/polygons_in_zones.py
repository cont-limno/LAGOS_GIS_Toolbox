#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      smithn78
#
# Created:     21/05/2014
# Copyright:   (c) smithn78 2014
# Licence:     <your licence>
#-------------------------------------------------------------------------------
import os
import arcpy
import csiutils as cu

def polygons_in_zones(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr, contrib_area = True):
    old_workspace = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)

    temp_polyzones = cu.create_temp_GDB('temp_polyzones')
    selected_polys = os.path.join(temp_polyzones, 'selected_polys')
    if interest_selection_expr:
        arcpy.Select_analysis(polygons_of_interest, selected_polys, interest_selection_expr)
    else:
        arcpy.CopyFeatures_management(polygons_of_interest, selected_polys)

    arcpy.AddField_management(selected_polys, 'POLYAREA_ha', 'DOUBLE')
    arcpy.CalculateField_management(selected_polys, 'POLYAREA_ha', '!shape.area@hectares!', 'PYTHON')

    # use tabulate intersection for the areas overlapping
    tab_table = 'tabulate_intersection_table'
    arcpy.TabulateIntersection_analysis(zone_fc, zone_field, selected_polys,
                                        tab_table)

    # area was calculated in map units which was m2 so convert to hectares
    arcpy.AddField_management(tab_table, 'Poly_Overlapping_AREA_ha', 'DOUBLE')
    arcpy.CalculateField_management(tab_table, 'Poly_Overlapping_AREA_ha', '!AREA!/10000', 'PYTHON')


    # just change the name of the percent field
    cu.rename_field(tab_table, 'PERCENTAGE', 'Poly_Overlapping_AREA_pct', True)
    spjoin_fc = 'spatial_join_output'

    # Spatial join for the count and contributing area
    fms = arcpy.FieldMappings()

    fm_zone_id = arcpy.FieldMap()
    fm_zone_id.addInputField(zone_fc, zone_field)

    fm_count = arcpy.FieldMap()
    fm_count.addInputField(selected_polys, 'POLYAREA_ha')
    count_name = fm_count.outputField
    count_name.name = 'Poly_Count'
    count_name.alias = 'Poly_Count'
    fm_count.outputField = count_name
    fm_count.mergeRule = 'Count'

    fm_contrib_area = arcpy.FieldMap()
    fm_contrib_area.addInputField(selected_polys, 'POLYAREA_ha')
    contrib_area_name = fm_contrib_area.outputField
    contrib_area_name.name = 'Poly_Contributing_AREA_ha'
    contrib_area_name.alias = 'Poly_Contributing_AREA_ha'
    fm_contrib_area.outputField = contrib_area_name
    fm_contrib_area.mergeRule = 'Sum'

    fms.addFieldMap(fm_zone_id)
    fms.addFieldMap(fm_count)
    fms.addFieldMap(fm_contrib_area)

    arcpy.SpatialJoin_analysis(zone_fc, selected_polys, spjoin_fc,
                                 "JOIN_ONE_TO_ONE", "KEEP_ALL", fms,
                                 "INTERSECT")

    arcpy.JoinField_management(tab_table, zone_field, spjoin_fc, zone_field, ["Poly_Count", "Poly_Contributing_AREA_ha"])
    final_fields = ['Poly_Overlapping_AREA_ha', 'Poly_Overlapping_AREA_pct', 'Poly_Count', 'Poly_Contributing_AREA_ha']

    # make output nice
    cu.one_in_one_out(tab_table, final_fields, zone_fc, zone_field, output_table)
    cu.redefine_nulls(output_table, final_fields, [0, 0, 0, 0])

    # clean up
    for item in [selected_polys, tab_table, spjoin_fc]:
        arcpy.Delete_management(item)
    arcpy.Delete_management(temp_polyzones)
    arcpy.env.workspace = old_workspace

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    polygons_of_interest = arcpy.GetParameterAsText(2)
    interest_selection_expr = arcpy.GetParameterAsText(3)
    output_table = arcpy.GetParameterAsText(4)
    polygons_in_zones(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr, True)

def test():
    zone_fc = r'C:\Users\smithn78\CSI_Processing\CSI\TestData_0411.gdb\HU12'
    zone_field = 'ZoneID'
    polygons_of_interest = r'C:\Users\smithn78\CSI_Processing\CSI\TestData_0411.gdb\Wetlands'
    interest_selection_expr = ''
    output_table = 'C:/GISData/Scratch/Scratch.gdb/POLYZONE_TEST_SEP18'
    polygons_in_zones(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr, True)

if __name__ == '__main__':
    main()
