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

# requires higher than ArcGIS 10.1--uses in_memory workspace that allows access to the geometry
def polygons_in_zones(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr):
    old_workspace = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)

    selected_polys = 'selected_polys'
    arcpy.AddMessage('Copying/selecting polygon features...')
    if interest_selection_expr:
        arcpy.Select_analysis(polygons_of_interest, selected_polys, interest_selection_expr)
    else:
        arcpy.CopyFeatures_management(polygons_of_interest, selected_polys)

    arcpy.AddField_management(selected_polys, 'POLYAREA_ha', 'DOUBLE')
    arcpy.CalculateField_management(selected_polys, 'POLYAREA_ha', '!shape.area@hectares!', 'PYTHON')

    # use tabulate intersection for the areas overlapping
    arcpy.AddMessage('Tabulating intersection between zones and polygons...')
    tab_table = arcpy.TabulateIntersection_analysis(zone_fc, zone_field, selected_polys,
                                        'tabulate_intersection_table')

    # area was calculated in map units which was m2 so convert to hectares
    arcpy.AddField_management(tab_table, 'Poly_Ha', 'DOUBLE')
    arcpy.CalculateField_management(tab_table, 'Poly_Ha', '!AREA!/10000', 'PYTHON')


    # just change the name of the percent field
    arcpy.AlterField_management(tab_table, 'PERCENTAGE', 'Poly_Pct')

    # Now just get the count as there is no other area metric anymore
    spjoin_fc = arcpy.SpatialJoin_analysis(zone_fc, selected_polys, 'spatial_join_output')
    arcpy.AlterField_management(spjoin_fc, 'Join_Count', 'Poly_n')

    # Add the density
    arcpy.AddField_management(spjoin_fc, 'Poly_nperha', 'DOUBLE')
    arcpy.CalculateField_management(spjoin_fc, 'Poly_nperha', '!Poly_n!/!shape.area@hectares!', 'PYTHON')

    arcpy.AddMessage('Refining output...')
    arcpy.JoinField_management(tab_table, zone_field, spjoin_fc, zone_field, ["Poly_n", 'Poly_nperha'])
    final_fields = ['Poly_Ha', 'Poly_Pct', 'Poly_n', 'Poly_nperha']

    # make output nice
    cu.one_in_one_out(tab_table, final_fields, zone_fc, zone_field, output_table)

    cu.redefine_nulls(output_table, final_fields, [0, 0, 0, 0])

    # clean up
    arcpy.Delete_management('in_memory')
    arcpy.env.workspace = old_workspace

    arcpy.AddMessage('Polygons in zones tool complete.')

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    polygons_of_interest = arcpy.GetParameterAsText(2)
    interest_selection_expr = arcpy.GetParameterAsText(3)
    output_table = arcpy.GetParameterAsText(4)
    polygons_in_zones(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr)

if __name__ == '__main__':
    main()
