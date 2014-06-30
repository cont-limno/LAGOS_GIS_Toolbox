# Filename: Export2CSV.py
import csv, os
import arcpy

def TableToCSV(in_table, out_folder, new_table_name = ''):
    if new_table_name:
        name = new_table_name
    else:
        name = os.path.splitext(os.path.basename(in_table))[0]
    out_csv = os.path.join(out_folder, name + '.csv')
    fields = [f.name for f in arcpy.ListFields(in_table) if f.type <> 'Geometry' and f.name <> 'Shape_Area' and f.name <> 'Shape_Length' and f.name <> 'TARGET_FID']
    with open(out_csv, 'w') as f:
        f.write(','.join(fields)+'\n') #csv headers
        with arcpy.da.SearchCursor(in_table, fields) as cursor:
            for row in cursor:
                values = ['NA' if r is None else str(r) for r in row]
                f.write(','.join(values)+'\n')

def main():
    in_table = arcpy.GetParameterAsText(0)
    out_folder = arcpy.GetParameterAsText(1)
    TableToCSV(in_table, out_folder)

if __name__ == '__main__':
    main()
