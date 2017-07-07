import csv, os, shutil, sys, time
from tempfile import NamedTemporaryFile
import arcpy
import zonal_tabarea


def validate_control_file(control_file, filter=''):
    """ Validates many (not all) of the paths and settings in the raster job control file.
    :param control_file: A file using the the batch_control_file.csv template.
    :param filter: A tuple, length 2, describing the start and stop "JOBNUM" positions for this run.
    :return: True if file is fully valid, False if any problems exist
    """
    with open(control_file) as csv_file:
        reader = csv.DictReader(csv_file)
        linenum = 0
        problem_count = 0
        zones_missing_ids = []
        for line in reader:
            linenum += 1
            zone = line['Zone Path']
            raster = line['Raster Path']
            if not line['JOBNUM']:
                print("Add job number to line {}".format(linenum))
                problem_count += 1
            if not arcpy.Exists(zone):
                print("Zone feature class path not valid for line {}".format(linenum))
                problem_count += 1
            if not arcpy.Exists(raster):
                print("Raster path not valid for line {}".format(linenum))
                problem_count += 1
            if not arcpy.ListFields(zone, 'ZoneID') and zone not in zones_missing_ids:
                zones_missing_ids.append(zone)
                problem_count += 1
            # TODO: Add projection check for each

            # TODO: Add presence of NoData value for raster check
            if arcpy.GetRasterProperties_management(raster, "VALUETYPE").getOutput(0) < 5 and line[
                'Is Thematic'] <> 'Y':
                print("Check thematic flag for line {}".format(linenum))
                # no addition to problem_count
        if zones_missing_ids:
            print("The following zones are missing ZoneID fields: {}".format(', '.join(zones_missing_ids)))
    if problem_count == 0:
        return True
    else:
        return False


def batch_run(control_file, output_geodatabase, filter='', validate=True):
    """
    Runs the zonal_tabarea.py script repeatedly using control file parameters and saves some output to the control
    file to record what happened.
    :param control_file: A file using the the batch_control_file.csv template.
    :param filter: A tuple, length 2, describing the start and stop "JOBNUM" positions for this run.
    :return: None
    """
    # Optional validation step
    if validate:
        is_valid_file = validate_control_file(control_file, filter)
        if not is_valid_file:
            sys.exit("Control file validation failed and batch run not initiated. Fix listed errors and try again.")

    # Read the file and filter it for only some jobs if necessary
    tempfile = NamedTemporaryFile()
    with open(control_file) as csv_file:
        reader = csv.DictReader(csv_file)
        field_names = reader.fieldnames
        writer = csv.DictWriter(csv_file, field_names)

        for line in reader:
            zone_fc = line['Zone Path']
            zone_field = 'ZoneID'
            in_value_raster = line['Raster Path']
            out_table = os.path.join(output_geodatabase, line['Output File Shortname'])
            is_thematic = line['Is Thematic']
            completions = int(line['Completions'])

            print("Creating {0}...Start Time {1}".format(out_table, time.strftime('%Y-%m-%d %H:%M:%S')))
            in_count = int(arcpy.GetCount_management(zone_fc)[0])

            try:
                result = zonal_tabarea.stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)
                latest_time = time.strftime('%Y-%m-%d %H:%M:%S')
                count_diff = result[1]
                completions += 1

            except Exception, e:
                # If it doesn't work, then don't change the "latest file" values for all of these
                out_table = line['Latest Output Path']
                in_count = line['In Count']
                count_diff = line['Count NULL']
                latest_time = line['Latest Completion Time']

            writer.writerow({'Completions': completions, 'Latest Output Path': out_table, 'In Count': in_count,
                             'Count NULL': count_diff, 'Latest Completion Time': latest_time})

            arcpy.ResetEnvironments()

    shutil.move(tempfile.name, control_file)


def main():
    CONTROL_FILE = ''
    OUTPUT_GEODATABASE = ''
    FILTER = ''
    batch_run(CONTROL_FILE, OUTPUT_GEODATABASE, FILTER)


def test():
    CONTROL_FILE = r"C:\Users\smithn78\Documents\Nicole temp\test_batch_run.csv"
    OUTPUT_GEODATABASE = r'C:\Users\smithn78\Documents\ArcGIS\Default.gdb'
    # FILTER = (1,1)
    batch_run(CONTROL_FILE, OUTPUT_GEODATABASE)


if __name__ == '__main__':
    main()
