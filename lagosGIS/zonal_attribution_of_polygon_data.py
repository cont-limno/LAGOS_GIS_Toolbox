import os
import arcpy

def zonal_attribution_of_polygon_data(zone_fc, zone_field, class_fc, output_table, class_field, class_name):
    arcpy.env.workspace = 'in_memory'
    tab = arcpy.TabulateIntersection_analysis(zone_fc, zone_field, class_fc, 'tab', class_field)
    pivot = arcpy.PivotTable_management(tab, zone_field, class_field, "PERCENTAGE", 'pivot')
    fnames = [f.name for f in arcpy.ListFields(pivot) if f.type not in ('OID', 'Geometry')]
    fnames.remove(zone_field)
    print(fnames)
    for f in fnames:
        zone_prefix = os.path.basename(zone_fc)
        new_fname = '{}_{}_{}_pct'.format(zone_prefix, class_name, f).lower()
        arcpy.AlterField_management(pivot, f, new_fname, clear_field_alias=True)
    arcpy.CopyRows_management(pivot, output_table)
    for item in [tab, pivot]:
        arcpy.Delete_management(item)

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    class_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    class_field = arcpy.GetParameterAsText(4)
    class_name = arcpy.GetParameterAsText(5)
    zonal_attribution_of_polygon_data(zone_fc, zone_field, class_fc, output_table, class_field, class_name)

if __name__ == '__main__':
    main()