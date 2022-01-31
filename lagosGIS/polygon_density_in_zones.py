# filename: polygon_density_in_zones.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)

import arcpy


# requires higher than ArcGIS 10.1--uses in_memory workspace that allows access to the geometry
import lagosGIS


def calc(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr):
    old_workspace = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'
    arcpy.SetLogHistory(False)
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    selected_polys = 'selected_polys'
    # fixes some stupid ArcGIS thing with the interactive Python window
    if arcpy.Exists(selected_polys):
        arcpy.env.overwriteOutput = True

    arcpy.AddMessage('Copying/selecting polygon features...')
    if interest_selection_expr:
        arcpy.Select_analysis(polygons_of_interest, selected_polys, interest_selection_expr)
    else:
        arcpy.CopyFeatures_management(polygons_of_interest, selected_polys)

    # use tabulate intersection for the areas overlapping
    arcpy.AddMessage('Tabulating intersection between zones and polygons...')
    tab_table = arcpy.TabulateIntersection_analysis(zone_fc, zone_field, selected_polys,
                                        'tabulate_intersection_table')

    # area was calculated in map units which was m2 so convert to hectares
    arcpy.AddField_management(tab_table, 'Poly_ha', 'DOUBLE')
    arcpy.CalculateField_management(tab_table, 'Poly_ha', '!AREA!/10000', 'PYTHON')


    # just change the name of the percent field
    arcpy.AlterField_management(tab_table, 'PERCENTAGE', 'Poly_pct')
    arcpy.CalculateField_management(tab_table, 'Poly_pct', 'min(!Poly_pct!, 100)', 'PYTHON') # fix rar val slightly 100+

    # Now just get the count as there is no other area metric anymore

    # stupid bit of code that allows at least a few pre-existing "Join_Count" fields to
    # not mess up the next bit in which we re-name that output field
    join_count_fnames = ['Join_Count', 'Join_Count_1', 'Join_Count_12']

    for fname in join_count_fnames:
        if arcpy.ListFields(selected_polys, fname):
            continue
        else:
            join_count_field_name = fname
            break

    # and now we proceed with said join
    spjoin_fc = arcpy.SpatialJoin_analysis(zone_fc, selected_polys, 'spatial_join_output')
    arcpy.AlterField_management(spjoin_fc, join_count_field_name, 'Poly_n')

    # Add the density
    arcpy.AddField_management(spjoin_fc, 'Poly_nperha', 'DOUBLE')
    arcpy.CalculateField_management(spjoin_fc, 'Poly_nperha', '!Poly_n!/!shape.area@hectares!', 'PYTHON')

    arcpy.AddMessage('Refining output...')
    arcpy.JoinField_management(tab_table, zone_field, spjoin_fc, zone_field, ["Poly_n", 'Poly_nperha'])
    final_fields = ['Poly_ha', 'Poly_pct', 'Poly_n', 'Poly_nperha']

    # make output nice
    arcpy.env.overwriteOutput = False
    lagosGIS.one_in_one_out(tab_table, zone_fc, zone_field, output_table)

    lagosGIS.redefine_nulls(output_table, final_fields, [0, 0, 0, 0])

    # clean up
    # can't delete all of in_memory because this function is meant to be called from another one that uses in_memory
    for item in [selected_polys, tab_table, spjoin_fc]:
        arcpy.Delete_management(item)
    arcpy.env.workspace = old_workspace

    arcpy.AddMessage('Polygons in zones tool complete.')
    arcpy.SetLogHistory(True)

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    polygons_of_interest = arcpy.GetParameterAsText(2)
    interest_selection_expr = arcpy.GetParameterAsText(3)
    output_table = arcpy.GetParameterAsText(4)
    calc(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr)

if __name__ == '__main__':
    main()
