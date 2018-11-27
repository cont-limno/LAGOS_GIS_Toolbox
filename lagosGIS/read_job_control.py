import csv
import os
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

    def cook_string(input):
        if input.startswith('r\'') and input.endswith('\''):
            return input[2:-1]
        else:
            return input

    for line in lines:
        function = cook_string(line['Function'])
        arg1 = cook_string(line['Arg1'])
        arg2 = cook_string(line['Arg2'])
        arg3 = cook_string(line['Arg3'])
        arg4 = cook_string(line['Arg4'])
        output = cook_string(line['Output'])
        calls.append("lagosGIS.{f}(r'{a1}', r'{a2}', r'{a3}', r'{a4}')".format(
            f = function,
            a1 = arg1,
            a2 = arg2,
            a3 = arg3,
            a4 = arg4))

    for call in calls:
        output_dir = os.path.dirname(output)
        if not arcpy.Exists(output_dir):
            raise Exception("Provide a valid geodatabase for the output.")
        if not arcpy.Exists(output):
            print(call)
            eval(call)

