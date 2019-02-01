import csv
import os
import time
import arcpy
import lagosGIS

def read_job_control(job_control_csv, start_line = -1, end_line = -1):
    """
    Reads a job control file with the following CSV format: First column contains function name to run. Columns contain arguments to use, in order.
    :param job_control_csv: The path to the job control CSV file
    :return: A list of function calls.
    """
    with open(job_control_csv) as csv_file:
        reader = csv.DictReader(csv_file)
        lines = [line for line in reader]
        if start_line > 0 or end_line > 0:
            lines = lines[start_line-1:end_line]

    calls = []
    outputs = []
    csv_paths = []
    def cook_string(input):
        """
        This function takes a "raw" string contained inside another string and makes it just a plain string.
        :param input: A string with contents that include r'[text'.
        :return: String
        """
        if input.startswith('r\'') and input.endswith('\''):
            return input[2:-1]
        else:
            return input

    # Read the table and compose the calls
    for line in lines:
        function = cook_string(line['Function'])
        arg1 = cook_string(line['Arg1'])
        arg2 = cook_string(line['Arg2'])
        arg3 = cook_string(line['Arg3'])
        arg4 = cook_string(line['Arg4'])
        arg5 = cook_string(line['Arg5'])
        output = cook_string(line['Output'])
        csv_path = cook_string(line['CSV'])
        outputs.append(output)
        csv_paths.append(csv_path)
        if arg5:
            calls.append("lagosGIS.{f}(r'{a1}', r'{a2}', r'{a3}', r'{a4}', r'{a5}')".format(
                f=function,
                a1=arg1,
                a2=arg2,
                a3=arg3,
                a4=arg4,
                a5=arg5))
        else:
            calls.append("lagosGIS.{f}(r'{a1}', r'{a2}', r'{a3}', r'{a4}')".format(
            f = function,
            a1 = arg1,
            a2 = arg2,
            a3 = arg3,
            a4 = arg4))

    # Call each tool and export the result to CSV
    for call, output, csv_path in zip(calls, outputs, csv_paths):
        output_dir = os.path.dirname(output)
        if not arcpy.Exists(output_dir):
            raise Exception("Provide a valid geodatabase for the output.")
        if not arcpy.Exists(output):
            print time.ctime()
            print(call)
            eval(call)

            out_folder = os.path.dirname(csv_path)
            out_basename = os.path.splitext(os.path.basename(csv_path))[0]
            lagosGIS.export_to_csv(output, out_folder, new_table_name=out_basename)

        # Keep in_memory workspace from carrying over to the next call
        arcpy.Delete_management('in_memory')

