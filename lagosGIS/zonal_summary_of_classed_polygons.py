import csv
import os
import arcpy
import lagosGIS


def summarize(zone_fc, zone_field, class_fc, out_table, class_field, rename_tag=''):

    def rename_to_standard(table, numeric=False):
        arcpy.AddMessage("Renaming.")

        # look up the values based on the rename tag
        this_files_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(this_files_dir)
        geo_file = os.path.abspath('../geo_metric_provenance.csv')
        with open(geo_file) as csv_file:
            reader = csv.DictReader(csv_file)
            mapping = {row['subgroup_original_code']: row['subgroup']
                       for row in reader if row['main_feature'] in rename_tag and row['main_feature']}
            if numeric:
                mapping = {'{}{}'.format(class_field, k):v for k, v in mapping.items()}
            arcpy.AddMessage(mapping)

        # update them
        for old, new in mapping.items():
            old_fname = '{}'.format(old)
            new_fname = '{}_{}_pct'.format(rename_tag, new)
            if arcpy.ListFields(table, old_fname):
                try:
                    # same problem with AlterField limit of 31 characters here.
                    arcpy.AlterField_management(table, old_fname, new_fname, clear_field_alias=True)
                except:
                    lagosGIS.rename_field(table, old_fname, new_fname, deleteOld=True)
        return table


    arcpy.env.workspace = 'in_memory'
    tab = arcpy.TabulateIntersection_analysis(zone_fc, zone_field, class_fc, 'tab', class_field, xy_tolerance='0.001 Meters')
    print([f.name for f in arcpy.ListFields(tab)])
    # guard against all numeric values--can't pivot when that is the case
    vals = [r[0] for r in arcpy.da.SearchCursor(tab, class_field)]
    all_numeric = all([str.isdigit(str(v)) for v in vals])
    if all_numeric:
        with arcpy.da.UpdateCursor(tab, class_field) as cursor:
            for row in cursor:
                row[0] = '{}{}'.format(class_field, row[0])
                cursor.updateRow(row)
    pivot = arcpy.PivotTable_management(tab, zone_field, class_field, "PERCENTAGE", 'pivot')
    renamed = rename_to_standard(pivot, all_numeric)

    # make sure all input zones have an output row, and where there was no data, consider this a 0 value, assuming
    # the vector data was comprehensive.
    # also replace values over 100% with 100. Getting a few of these (like 100.0000003) even with a good tolerance.
    all_zones = lagosGIS.one_in_one_out(renamed, zone_fc, zone_field, 'all_zones')
    new_fields = [f.name for f in arcpy.ListFields(all_zones) if f.name <> zone_field and f.type not in ('OID', 'Geometry')]
    with arcpy.da.UpdateCursor(all_zones, new_fields) as cursor:
        for row in cursor:
            row = [min(val, 100) if val else 0 for val in row]
            cursor.updateRow(row)

    arcpy.CopyRows_management(all_zones, out_table)
    for item in [tab, pivot, renamed]:
        arcpy.Delete_management(item)

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    class_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    class_field = arcpy.GetParameterAsText(4)
    rename_tag = arcpy.GetParameterAsText(5)
    summarize(zone_fc, zone_field, class_fc, output_table, class_field, rename_tag)

if __name__ == '__main__':
    main()