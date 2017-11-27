# Filename: Export2CSV.py
import csv, datetime, os, math, re
import arcpy
import csiutils as cu
from decimal import *

def TableToCSV(in_table, out_folder, output_schema = True, export_qa_version = True, field_list = [], new_table_name = ''):
    if new_table_name:
        name = new_table_name
    else:
        name = os.path.splitext(os.path.basename(in_table))[0]
    out_qa_csv = os.path.join(out_folder, "{}_QA_ONLY.csv".format(name))
    out_csv = os.path.join(out_folder, "{}.csv".format(name))
    if field_list:
        fields_qa = field_list
    else:
        fields_qa = [f.name for f in arcpy.ListFields(in_table) if f.type <> 'Geometry' and f.type <> 'OID' and f.name <> 'Shape_Area' and f.name <> 'Shape_Length' and f.name <> 'TARGET_FID']
    ha_prefix = tuple(["Ha_{}".format(d) for d in range(10)])
    fields = [f for f in fields_qa if not f.startswith(ha_prefix)]

    if export_qa_version:
        with open(out_qa_csv, 'w') as f:
            f.write(','.join(fields_qa) + '\n')  # csv headers
            with arcpy.da.SearchCursor(in_table, fields_qa) as cursor:
                for row in cursor:
                    # next line PREVENTS scientific notation in exports and change null values

                    def format_value(x):
                        try:
                            if math.isnan(x):
                                return 'NULL'
                        except:
                            pass
                        if x is None:
                            return 'NULL'
                        elif isinstance(x, float):
                            d = Decimal(x)
                            out_value = str(d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize())
                            if out_value == '-0':
                                out_value = '0'
                            return out_value
                        elif isinstance(x, int):
                            return str(x)
                        elif isinstance(x, unicode):
                            return x.encode('utf-8')
                        elif isinstance(x, datetime.datetime):
                            return str(x)

                    values = map(format_value, row)
                    f.write(','.join(values) + '\n')

    with open(out_csv, 'w') as f:
        f.write(','.join(fields)+'\n') #csv headers
        with arcpy.da.SearchCursor(in_table, fields) as cursor:
            for row in cursor:
                # next line PREVENTS scientific notation in exports and change null values

                def format_value(x):
                    try:
                        if math.isnan(x):
                            return 'NULL'
                    except:
                        pass
                    if x is None:
                        return 'NULL'
                    elif isinstance(x, float):
                        d = Decimal(x)
                        out_value = str(d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize())
                        if out_value == '-0':
                            out_value = '0'
                        return out_value
                    elif isinstance(x, int):
                        return str(x)
                    elif isinstance(x, unicode):
                        return x.encode('utf-8')
                    elif isinstance(x, datetime.datetime):
                        return str(x)
                values = map(format_value, row)
                f.write(','.join(values)+'\n')

    if output_schema:
        out_schema = os.path.join(out_folder, "{}_schema.csv".format(name))
        cu.describe_arcgis_table_csv(in_table, out_schema, field_list)

def main():
    in_table = arcpy.GetParameterAsText(0)
    out_folder = arcpy.GetParameterAsText(1)
    output_schema = arcpy.GetParameter(2)
    TableToCSV(in_table, out_folder, output_schema)

if __name__ == '__main__':
    main()
