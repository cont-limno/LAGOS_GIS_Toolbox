# filename: export_to_csv.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS, GEO, CONN
# tool type: re-usable (ArcGIS Toolbox)

import csv
import datetime
import os
import math
from tempfile import NamedTemporaryFile
import shutil
import arcpy


def describe_arcgis_table_csv(in_table, out_path, field_list = [], rename_fields = True):
    """
    :param in_table: A feature class or table used by ArcCatalog.
    :param out_path: Where to save the output. Defaults to the input table named appended with "_cols.csv"
    :return: None
    """
    all_fields = arcpy.ListFields(in_table)
    if field_list:
        fields = [f for f in all_fields if f.name in field_list]
    else:
        fields = all_fields
    string_fields = [f.name for f in fields if f.type == 'String']
    if string_fields:
        try:
            arr = arcpy.da.TableToNumpyArray(in_table, string_fields)
        except:
            arr = arcpy.da.FeatureClassToNumPyArray(in_table, string_fields)

        #gets the maximum string length for each field and returns a dictionary named with the fields
        string_lengths = dict(zip(string_fields, [len(max(arr[f], key=len)) for f in string_fields]))
    else:
        string_lengths = {}

    with open(out_path, 'wb') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=[
            'column_name', 'column_esri_type', 'column_esri_length', 'column_string_min'])
        writer.writeheader()

        for f in fields:
            if rename_fields: # this code is the duplicated part that I don't like that much.
                if 'OBJECTID' in f.name:
                    continue
                short_f_orig = os.path.splitext(os.path.basename(in_table))[0]
                short_f = short_f_orig.replace('_QA_ONLY', '')
                f.name = '{}_{}'.format(short_f, f.name).lower()

            if f.name in string_lengths:
                shortest = string_lengths[f.name]
            else:
                shortest = ''
            out_dict = {'column_name': f.name, 'column_esri_type': f.type, 'column_esri_length': f.length, \
                        'column_string_min': shortest}
            writer.writerow(out_dict)
    return(out_path)

def rename_variables(file, prefix = ''):
    tempfile = NamedTemporaryFile(delete=False)
    if prefix:
        short_f = prefix
    else:
        short_f_orig = os.path.splitext(os.path.basename(file))[0]
        short_f = short_f_orig.replace('_QA_ONLY', '')

    with open(file, 'rb') as csv_file:
        reader = csv.DictReader(csv_file)
        header = reader.fieldnames

        #update the header
        desired_header = ['{}_{}'.format(short_f, name).lower() if 'zoneid' not in name else name for name in header]
        update_dict = dict(zip(header, desired_header))
        filtered_header = [name for name in desired_header if 'OBJECT' not in name]

        # write out selected fields with new names
        with tempfile:
            writer = csv.DictWriter(tempfile, fieldnames = filtered_header)
            writer.writeheader()
            for row in reader:
                new_row = {update_dict[k]: row[k] for k in row if update_dict[k] in filtered_header}
                writer.writerow(new_row)

    shutil.move(tempfile.name, file)

def TableToCSV(in_table, out_folder, output_schema = True, prefix = '', new_table_name = '',
               rename_fields = True, export_qa_version = True, field_list = []):
    if arcpy.env.workspace == 'in_memory' and ':' not in in_table:
        name = os.path.basename(str(in_table))
    else:
        name = os.path.splitext(os.path.basename(in_table))[0]
    out_qa_csv = os.path.join(out_folder, "{}_QA_ONLY.csv".format(name))
    out_csv = os.path.join(out_folder, "{}.csv".format(name))
    arcpy.AddMessage("out csv is {}".format(out_csv))

    # for rounding
    places = 10

    if field_list:
        fields_qa = field_list
    else:
        fields_qa = [f.name for f in arcpy.ListFields(in_table) if f.type <> 'Geometry' and f.type <> 'OID' and f.name <> 'Shape_Area' and f.name <> 'Shape_Length' and f.name <> 'TARGET_FID']
    ha_prefix = tuple(["Ha_{}".format(d) for d in range(10)])
    fields = [f for f in fields_qa if not f.startswith(ha_prefix) and f not in ['CELL_COUNT', 'ORIGINAL_COUNT']]

    def format_value(x):
        """PREVENTS scientific notation in exports and change null values"""
        try:
            if math.isnan(x):
                return 'NULL'
        except:
            pass
        if x is None:
            return 'NULL'
        elif isinstance(x, float):
            x_10 = round(x, 10)
            x_int = int(round(x, 0))
            out_value = str(x_int if x_10 == x_int else '{:.10f}'.format(x_10))
            if out_value == '-0':
                out_value = '0'
            return out_value
        elif isinstance(x, int):
            return str(x)
        elif isinstance(x, unicode) or isinstance(x, str):
            if ',' in x:
                x = '"{}"'.format(x)  # quote-protection for commas
            return x.encode('utf-8')
        elif isinstance(x, datetime.datetime):
            return str(x)

    if export_qa_version:
        with open(out_qa_csv, 'w') as f:
            f.write(','.join(fields_qa) + '\n')  # csv headers
            with arcpy.da.SearchCursor(in_table, fields_qa) as cursor:
                for row in cursor:
                    values = map(format_value, row)
                    f.write(','.join(values) + '\n')

    with open(out_csv, 'w') as f:
        f.write(','.join(fields)+'\n') #csv headers
        with arcpy.da.SearchCursor(in_table, fields) as cursor:
            for row in cursor:
                values = map(format_value, row)
                f.write(','.join(values)+'\n')

    if rename_fields:
        rename_variables(out_csv, prefix)
        rename_variables(out_qa_csv, prefix)

    if output_schema:
        out_schema = os.path.join(out_folder, "{}_schema.csv".format(name))
        out_schema = describe_arcgis_table_csv(in_table, out_schema, field_list, rename_fields=rename_fields)

    if new_table_name:
        out_qa_csv_rename = os.path.join(out_folder, "{}_QA_ONLY.csv".format(new_table_name))
        out_csv_rename = os.path.join(out_folder, "{}.csv".format(new_table_name))
        out_schema_rename = os.path.join(out_folder, "{}_schema.csv".format(new_table_name))
        os.rename(out_csv, out_csv_rename)
        if export_qa_version:
            os.rename(out_qa_csv, out_qa_csv_rename)
        if output_schema:
            os.rename(out_schema, out_schema_rename)


def main():
    in_table = arcpy.GetParameterAsText(0)
    out_folder = arcpy.GetParameterAsText(1)
    output_schema = arcpy.GetParameter(2)
    rename_fields = arcpy.GetParameter(3)
    prefix = arcpy.GetParameter(4)
    new_table_name = arcpy.GetParameterAsText(5)
    TableToCSV(in_table, out_folder, output_schema, rename_fields=rename_fields, prefix=prefix, new_table_name=new_table_name)

if __name__ == '__main__':
    main()
