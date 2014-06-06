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

def polygons_in_zones(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr):
    arcpy.env.workspace = 'in_memory'
    if interest_selection_expr:
        arcpy.MakeFeatureLayer_management(polygons_of_interest, "selected_polys", interest_selection_expr)
    else:
        arcpy.MakeFeatureLayer_management(polygons_of_interest, "selected_polys")

    # use tabulate intersection for the areas because otherwise you get the
    # entire area of wetlands extending outside the zone and right now we
    # don't want that
    tab_table = 'tabulate_intersection_table'
    arcpy.TabulateIntersection_analysis(zone_fc, zone_field, "selected_polys",
                                        tab_table)
    cu.rename_field(tab_table, 'AREA', 'Poly_AREA_ha', True)
    cu.rename_field(tab_table, 'PERCENTAGE', 'Poly_AREA_pct', True)
    spjoin_fc = 'spatial_join_output'
    arcpy.SpatialJoin_analysis(zone_fc, "selected_polys", spjoin_fc,
                                 "JOIN_ONE_TO_ONE", "KEEP_ALL",
                                  match_option =  "INTERSECT")
    arcpy.AddField_management(spjoin_fc, "Poly_Count", 'Short')
    arcpy.CalculateField_management(spjoin_fc, "Poly_Count", '!Join_Count!', "PYTHON")

    arcpy.JoinField_management(tab_table, zone_field, spjoin_fc, zone_field, "Poly_Count")
    final_fields = ['Poly_AREA_ha', 'Poly_AREA_pct', 'Poly_Count']

    # make output nice
    cu.one_in_one_out(tab_table, final_fields, zone_fc, zone_field, output_table)
    cu.redefine_nulls(output_table, final_fields, [0, 0, 0])

    # clean up
    for item in ["selected_polys", tab_table, spjoin_fc]:
        arcpy.Delete_management(item)

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    polygons_of_interest = arcpy.GetParameterAsText(2)
    interest_selection_expr = arcpy.GetParameterAsText(3) # default should be set to """"ATTRIBUTE" LIKE 'P%'AND "WETLAND_TY" <> 'Freshwater_Pond'"""
    output_table = arcpy.GetParameterAsText(4)
    polygons_in_zones(zone_fc, zone_field, polygons_of_interest, interest_selection_expr, output_table)

def test():
    zone_fc = 'C:/GISData/Scratch/Scratch.gdb/HU12_test'
    zone_field = 'ZoneID'
    polygons_of_interest = 'C:/GISData/Scratch/Scratch.gdb/wetlands_test'
    interest_selection_expr = ''
    output_table = 'C:/GISData/Scratch/Scratch.gdb/polyzone_test'
    polygons_in_zones(zone_fc, zone_field, polygons_of_interest, interest_selection_expr, output_table)

if __name__ == '__main__':
    main()
