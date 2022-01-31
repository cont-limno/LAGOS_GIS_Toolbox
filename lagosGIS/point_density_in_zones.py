# filename: point_density_in_zones.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)

import os
import arcpy

def calc(zone_fc, zone_field, points_fc, output_table, interest_selection_expr ='', rename_label =''):
    arcpy.env.workspace = 'in_memory'
    if interest_selection_expr:
        arcpy.MakeFeatureLayer_management(points_fc, "selected_points", interest_selection_expr)
    else:
        arcpy.MakeFeatureLayer_management(points_fc, "selected_points")

    arcpy.SpatialJoin_analysis(zone_fc, "selected_points", 'temp_fc',
                            'JOIN_ONE_TO_ONE', 'KEEP_ALL',
                            match_option= 'INTERSECT')

    field_names = ['n', 'npersqkm']
    if rename_label:
        field_names = ['{}_{}'.format(rename_label, fn) for fn in field_names]
    field_types = ['LONG', 'DOUBLE']
    calc_expressions = ['!Join_Count!', '!Join_Count!/!shape.area@squarekilometers!']

    for fname, ftype, expr in zip(field_names, field_types, calc_expressions):
        arcpy.AddField_management('temp_fc', fname, ftype)
        arcpy.CalculateField_management('temp_fc', fname, expr, 'PYTHON')

    arcpy.CopyRows_management('temp_fc', output_table)
    keep_fields = [zone_field] + field_names
    out_fields = [f.name for f in arcpy.ListFields(output_table)]
    for f in out_fields:
        if f not in keep_fields:
            try:
                arcpy.DeleteField_management(output_table, f)
            except:
                continue
    arcpy.Delete_management('selected_points')
    arcpy.Delete_management('temp_fc')

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    points_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(4)
    interest_selection_expr = arcpy.GetParameterAsText(3)
    calc(zone_fc, zone_field, points_fc, output_table, interest_selection_expr)

def test():
    test_gdb = '../TestData_0411.gdb'
    zone_fc = os.path.join(test_gdb, 'HU12')
    zone_field = 'ZoneID'
    points_fc = os.path.join(test_gdb, 'Dams')
    output_table = 'C:/GISData/Scratch/Scratch.gdb/test_points_tool'
    calc(zone_fc, zone_field, points_fc, output_table, '')

if __name__ == '__main__':
    main()

