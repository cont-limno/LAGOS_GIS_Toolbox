# Filename: Export2CSV.py
import arcpy, os, csv

def TableToCSV(in_table, out_folder):
    name = os.path.splitext(os.path.basename(in_table))[0]
    out_csv = os.path.join(out_folder, name + '.csv')
    fields = [f.name for f in arcpy.ListFields(in_table) if f.type <> 'Geometry' and f.name <> 'Shape_Area' and f.name <> 'Shape_Length' and f.name <> 'TARGET_FID']
    with open(out_csv, 'w') as f:
        f.write(','.join(fields)+'\n') #csv headers
        with arcpy.da.SearchCursor(in_table, fields) as cursor:
            for row in cursor:
                f.write(','.join([str(r) for r in row])+'\n')

def main():
    in_table = arcpy.GetParameterAsText(0)
    out_folder = arcpy.GetParameterAsText(1)
    TableToCSV(in_table, out_folder)

if __name__ == '__main__':
    main()
