# filename: polygon_density_in_zones.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)

import arcpy


# requires higher than ArcGIS 10.1--uses in_memory workspace that allows access to the geometry
import lagosGIS


def calc(zone_fc, zone_field, polygons_of_interest, output_table, where_clause=''):
    """
    Calculates total area and percent of zonal polygon occupied by polygons of interest for polygon features such as
    lakes.
    :param zone_fc: Zones polygon feature class
    :param zone_field: Unique identifier for each zone
    :param polygons_of_interest: Polygon feature class to be summarized
    :param output_table: Output table to save the result
    :param where_clause: (Optional) Query (SQL where clause) to filter the polygons of interest before summary
    :return: None
    """

    # Setup
    old_workspace = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    selected_polys = 'selected_polys'
    if arcpy.Exists(selected_polys):
        arcpy.env.overwriteOutput = True

    if where_clause:
        arcpy.Select_analysis(polygons_of_interest, selected_polys, where_clause)
    else:
        arcpy.CopyFeatures_management(polygons_of_interest, selected_polys)

    # Calculate area and percentage of polygons of interest that overlap zones
    arcpy.AddMessage('Tabulating intersection between zones and polygons...')
    tab_table = arcpy.TabulateIntersection_analysis(zone_fc, zone_field, selected_polys,
                                        'tabulate_intersection_table')

    # Convert area to hectares from m2 and rename percentage
    arcpy.AddField_management(tab_table, 'Poly_ha', 'DOUBLE')
    arcpy.CalculateField_management(tab_table, 'Poly_ha', '!AREA!/10000', 'PYTHON')
    arcpy.AlterField_management(tab_table, 'PERCENTAGE', 'Poly_pct')
    arcpy.CalculateField_management(tab_table, 'Poly_pct', 'min(!Poly_pct!, 100)', 'PYTHON') # fix rar val slightly 100+

    # Guarantee that a new "Join_Count" field (produced with Spatial Join) is the one to use in upcoming calculations
    join_count_fnames = ['Join_Count', 'Join_Count_1', 'Join_Count_12']

    for fname in join_count_fnames:
        if arcpy.ListFields(selected_polys, fname):
            continue
        else:
            join_count_field_name = fname
            break

    # Spatial join to get count of polygons intersecting zone
    spjoin_fc = arcpy.SpatialJoin_analysis(zone_fc, selected_polys, 'spatial_join_output')
    arcpy.AlterField_management(spjoin_fc, join_count_field_name, 'Poly_n')

    # Add and calculate density field from count
    arcpy.AddField_management(spjoin_fc, 'Poly_nperha', 'DOUBLE')
    arcpy.CalculateField_management(spjoin_fc, 'Poly_nperha', '!Poly_n!/!shape.area@hectares!', 'PYTHON')
    arcpy.JoinField_management(tab_table, zone_field, spjoin_fc, zone_field, ["Poly_n", 'Poly_nperha'])
    final_fields = ['Poly_ha', 'Poly_pct', 'Poly_n', 'Poly_nperha']

    # Refine output, one row out for every one row in and null values mean 0 polygons in zone
    arcpy.env.overwriteOutput = False
    lagosGIS.one_in_one_out(tab_table, zone_fc, zone_field, output_table)

    lagosGIS.redefine_nulls(output_table, final_fields, [0, 0, 0, 0])

    # Cleanup
    for item in [selected_polys, tab_table, spjoin_fc]:
        arcpy.Delete_management(item)
    arcpy.env.workspace = old_workspace


def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    polygons_of_interest = arcpy.GetParameterAsText(2)
    interest_selection_expr = arcpy.GetParameterAsText(3)
    output_table = arcpy.GetParameterAsText(4)
    calc(zone_fc, zone_field, polygons_of_interest, output_table, interest_selection_expr)


if __name__ == '__main__':
    main()
