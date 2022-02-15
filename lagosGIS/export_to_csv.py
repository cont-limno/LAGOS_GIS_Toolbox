# filename: export_to_csv.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS, GEO, CONN
# tool type: re-usable (ArcGIS Toolbox)

import csv
import datetime
import os
import math
from tempfile import NamedTemporaryFile
import shutil
import arcpy


def describe_arcgis_table_csv(in_table, out_path, field_list=[], rename_fields=True):
    """
    Creates a companion table to a CSV table export that describes the field properties for each field as they were
    stored in the file geodatabase table.
    :param in_table: The feature class or table that will be exported to CSV
    :param out_path: The output table location
    :param field_list: (Optional) The list of fields to be described. Default is all fields.
    :param rename_fields: Whether the fields are to be renamed in the exported CSV table
    :return: The output table location
    """

    # Identify fields to be described
    all_fields = arcpy.ListFields(in_table)
    if field_list:
        fields = [f for f in all_fields if f.name in field_list]
    else:
        fields = all_fields

    # Define length for string fields as the longest character string value actually found in the table
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

    # Initialize  and populate output table with arcpy.Field object properties, unless string length

    with open(out_path, 'wb') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=['column_name',
                                                      'column_esri_type',
                                                      'column_esri_length',
                                                      'column_string_min'
                                                      ]
                                )
        writer.writeheader()

        for f in fields:
            # Re-name fields with necessary
            if rename_fields: # duplicated from below, not my favorite way
                if 'OBJECTID' in f.name:
                    continue
                short_f_orig = os.path.splitext(os.path.basename(in_table))[0]
                short_f = short_f_orig.replace('_QA_ONLY', '')
                f.name = '{}_{}'.format(short_f, f.name).lower()

            if f.name in string_lengths:
                shortest = string_lengths[f.name]
            else:
                shortest = ''

            # Write out the results
            out_dict = {'column_name': f.name,
                        'column_esri_type': f.type,
                        'column_esri_length': f.length,
                        'column_string_min': shortest
                        }
            writer.writerow(out_dict)

    return out_path


def rename_variables(csv_file, prefix=''):
    """
    Renames all variables in a CSV file with the specified prefix or assumes the prefix from the file name.
    :param csv_file: The CSV file in which to rename columns/fields
    :param prefix: Text string of the prefix to use for all columns/fields
    :return: None
    """

    tempfile = NamedTemporaryFile(delete=False)

    # Identify the prefix to use
    if prefix:
        short_f = prefix
    else:
        short_f_orig = os.path.splitext(os.path.basename(csv_file))[0]
        short_f = short_f_orig.replace('_QA_ONLY', '')

    # Read and modify the column names
    with open(csv_file, 'rb') as csv_file:
        reader = csv.DictReader(csv_file)
        header = reader.fieldnames

        # Update the header with new names
        desired_header = ['{}_{}'.format(short_f, name).lower() if 'zoneid' not in name else name for name in header]
        update_dict = dict(zip(header, desired_header))
        filtered_header = [name for name in desired_header if 'OBJECT' not in name]

        # Write out values for each field with new names
        with tempfile:
            writer = csv.DictWriter(tempfile, fieldnames = filtered_header)
            writer.writeheader()
            for row in reader:
                new_row = {update_dict[k]: row[k] for k in row if update_dict[k] in filtered_header}
                writer.writerow(new_row)

    # Update the original CSV file with the temp and delete the temp
    shutil.move(tempfile.name, csv_file)
    os.remove(tempfile.name)


def format_value(x):
    """Prevent scientific notation in exports and change missing values to 'NULL' string."""
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


def export(in_table, out_folder, output_schema=True, prefix='', new_table_name='',
           rename_fields=True, export_qa_version=True, field_list=[]):
    """
    Exports a CSV with suppression of scientific notation and with options to rename fields and output a data schema
    table.

    You can use Export Rows to export tables instead of this tool if you do not need any of the specific functionality.
    :param in_table: A table to be converted to CSV
    :param out_folder: The directory in which the CSV output(s) will be located
    :param output_schema: (Optional) Boolean, default True. Whether to create a descriptive data schema table.
    :param prefix: (Optional) A text string containing a prefix to append to all output column names
    :param new_table_name: (Optional) A new name to use for the output table, if desired. The table will have the same
    name as the input table by default.
    :param rename_fields: (Optional) Boolean, default True
    :param export_qa_version: (Optional) Boolean, default True
    :param field_list: A list of column names to save in the output
    :return: None
    """

    # Get file basename without extension and specify auxiliary table output paths
    if arcpy.env.workspace == 'in_memory' and ':' not in in_table:
        name = os.path.basename(str(in_table))
    else:
        name = os.path.splitext(os.path.basename(in_table))[0]
    out_qa_csv = os.path.join(out_folder, "{}_QA_ONLY.csv".format(name))
    out_csv = os.path.join(out_folder, "{}.csv".format(name))
    arcpy.AddMessage("out csv is {}".format(out_csv))

    # Specify fields to use in outputs; select areas from Zonal Summary of Raster Data for special QA treatment
    if field_list:
        fields_qa = field_list
    else:
        fields_qa = [f.name for f in arcpy.ListFields(in_table) if f.type <> 'Geometry' and f.type <> 'OID' and f.name <> 'Shape_Area' and f.name <> 'Shape_Length' and f.name <> 'TARGET_FID']
    ha_prefix = tuple(["Ha_{}".format(d) for d in range(10)])
    fields = [f for f in fields_qa if not f.startswith(ha_prefix) and f not in ['CELL_COUNT', 'ORIGINAL_COUNT']]

    # Export QA version of file, if elected
    if export_qa_version:
        with open(out_qa_csv, 'w') as f:
            f.write(','.join(fields_qa) + '\n')  # csv headers
            with arcpy.da.SearchCursor(in_table, fields_qa) as cursor:
                for row in cursor:
                    values = map(format_value, row)
                    f.write(','.join(values) + '\n')

    # Export table with original names to the output location
    with open(out_csv, 'w') as f:
        f.write(','.join(fields)+'\n') #csv headers
        with arcpy.da.SearchCursor(in_table, fields) as cursor:
            for row in cursor:
                values = map(format_value, row)
                f.write(','.join(values)+'\n')

    # Modify the field names in place, if elected
    if rename_fields:
        rename_variables(out_csv, prefix)
        rename_variables(out_qa_csv, prefix)

    # Create the data schema description table, if elected
    if output_schema:
        out_schema = os.path.join(out_folder, "{}_schema.csv".format(name))
        out_schema = describe_arcgis_table_csv(in_table, out_schema, field_list, rename_fields=rename_fields)

    # Modify the table file name, if elected
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
    export(in_table, out_folder, output_schema, rename_fields=rename_fields, prefix=prefix, new_table_name=new_table_name)


if __name__ == '__main__':
    main()
