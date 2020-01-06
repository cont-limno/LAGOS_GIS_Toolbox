import csv
import os
import arcpy
import csiutils as cu


def zonal_attribution_of_polygon_data(zone_fc, zone_field, class_fc, out_table, class_field, rename_tag=''):

    def rename_to_standard(table):
        arcpy.AddMessage("Renaming.")

        # look up the values based on the rename tag
        this_files_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(this_files_dir)
        geo_file = os.path.abspath('../geo_metric_provenance.csv')
        with open(geo_file) as csv_file:
            reader = csv.DictReader(csv_file)
            mapping = {row['subgroup_original_code']: row['subgroup']
                       for row in reader if row['main_feature'] in rename_tag and row['main_feature']}
            arcpy.AddMessage(mapping)

        # update them
        for old, new in mapping.items():
            arcpy.AddMessage(new)
            old_fname = '{}'.format(old)
            new_fname = '{}_{}_pct'.format(rename_tag, new)
            if arcpy.ListFields(table, old_fname):
                try:
                    # same problem with AlterField limit of 31 characters here.
                    arcpy.AlterField_management(table, old_fname, new_fname, clear_field_alias=True)
                except:
                    cu.rename_field(table, old_fname, new_fname, deleteOld=True)
        return table


    arcpy.env.workspace = 'in_memory'
    tab = arcpy.TabulateIntersection_analysis(zone_fc, zone_field, class_fc, 'tab', class_field)
    pivot = arcpy.PivotTable_management(tab, zone_field, class_field, "PERCENTAGE", 'pivot')
    renamed = rename_to_standard(pivot)
    arcpy.CopyRows_management(renamed, out_table)
    for item in [tab, pivot, renamed]:
        arcpy.Delete_management(item)

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    class_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    class_field = arcpy.GetParameterAsText(4)
    rename_tag = arcpy.GetParameterAsText(5)
    zonal_attribution_of_polygon_data(zone_fc, zone_field, class_fc, output_table, class_field, rename_tag)

if __name__ == '__main__':
    main()