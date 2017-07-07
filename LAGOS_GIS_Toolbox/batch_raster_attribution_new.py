import csv, os, shutil, sys, time
import arcpy
from tempfile import NamedTemporaryFile
import zonal_tabarea


def validate_control_file(control_file, filter=''):
    """ Validates many (not all) of the paths and settings in the raster job control file. The following problems can
    be identified: Duplicate zone/raster combination, duplicate job number, missing job number, zones path does not
    exist, raster path does not exist, zones do not have ZoneID, projection is not USGS Albers. The following
    warning(s) can be issued: Check thematic flag value.
    :param control_file: A file using the the batch_control_file.csv template.
    :param filter: A tuple, length 2, describing the start and stop "JOBNUM" positions for this run.
    :return: True if file is fully valid, False if any problems exist
    """
    with open(control_file) as csv_file:
        reader = csv.DictReader(csv_file)
        linenum = 0
        problem_count = 0
        zones_missing_ids = []
        jobnum_set = set()
        combos_set = set()
        for line in reader:
            linenum += 1
            zone = line['Zone Path']
            raster = line['Raster Path']
            combo = zone + raster
            if combo in combos_set:
                print("ERROR: Duplicate zone/raster combination. Duplicate is found at line {}".format(linenum))
            else:
                combos_set.add(combo)
            jobnum = line['JOBNUM']

            if not jobnum:
                print("ERROR: Add job number to line {}".format(linenum))
                problem_count += 1
            else:
                if jobnum > filter[1] or jobnum < filter[0]:
                    continue
                if jobnum in jobnum_set:
                    print("ERROR: Duplicate job number. First duplication is at line {}".format(linenum))
                else:
                    jobnum_set.add(jobnum)
            if arcpy.Exists(zone):
                if not arcpy.ListFields(zone, 'ZoneID') and zone not in zones_missing_ids:
                    zones_missing_ids.append(zone)
                    problem_count += 1
            else:
                print("ERROR: Zone feature class path not valid for line {}".format(linenum))
                problem_count += 1
            if not arcpy.Exists(raster):
                print("ERROR: Raster path not valid for line {}".format(linenum))
                problem_count += 1

            # TODO: Add projection check for each
            print(arcpy.Describe(zone).spatialReference.factoryCode)

            if int(arcpy.GetRasterProperties_management(raster, "VALUETYPE").getOutput(0)) < 5 and line[
                'Is Thematic'] <> 'Y':
                print("WARNING: Check thematic flag for line {}".format(linenum))
                # no addition to problem_count
        for z in zones_missing_ids:
            print("ERROR: {} is missing a ZoneID field").format(z)
        time.sleep(1)  # keep other messages from interrupting list

    if problem_count == 0:
        return True
    else:
        return False


def batch_run(control_file, output_geodatabase, filter='', validate=True):
    """
    Runs the zonal_tabarea.py script repeatedly using control file parameters and saves some output to the control
    file to record what happened.
    :param control_file: A file using the the batch_control_file.csv template.
    :param output_geodatabase: Where the output tables will be created
    :param filter: A tuple, length 2, describing the start and stop "JOBNUM" positions for this run.
    :param validate: Boolean. If True, validate control file before permitting batch run.
    :return: None
    """
    # Optional validation step
    if validate:
        is_valid_control_file = validate_control_file(control_file, filter)
        if not is_valid_control_file:
            sys.exit(
                "ERROR: Control file validation failed and batch run not initiated. Fix listed errors and try again.")

    # Read the file and filter it for only some jobs if necessary
    tempfile = NamedTemporaryFile(delete=False)
    with open(control_file, 'rb') as csv_file, tempfile:
        reader = csv.DictReader(csv_file)
        field_names = reader.fieldnames
        writer = csv.DictWriter(tempfile, field_names)
        writer.writeheader()

        for line in reader:
            jobnum = line['Jobnum']
            if jobnum > filter[1] or jobnum < filter[0]:
                continue
            zone_fc = line['Zone Path']
            zone_field = 'ZoneID'
            in_value_raster = line['Raster Path']
            out_table_shortname = '{zone}_{raster}'.format(zone=os.path.splitext(os.path.basename(zone_fc))[0],
                                                           raster=os.path.splitext(os.path.basename(in_value_raster))[
                                                               0])
            out_table = os.path.join(output_geodatabase, out_table_shortname)
            if line['Is Thematic'] == 'Y':
                is_thematic = True
            else:
                is_thematic = False
            force_rerun = line['Force Rerun']

            # Do not re-run for any existing tables unless the flag is set in the control file
            if arcpy.Exists(out_table) and force_rerun <> 'Y':
                print("SKIPPING {0}...Time {1}".format(out_table, time.strftime('%Y-%m-%d %H:%M:%S')))
                write_line = line
                writer.writerow(write_line)
                continue

            else:
                print("Creating {0}...Start Time {1}".format(out_table, time.strftime('%Y-%m-%d %H:%M:%S')))
                in_count = int(arcpy.GetCount_management(zone_fc)[0])

                try:
                    result = zonal_tabarea.stats_area_table(zone_fc, zone_field, in_value_raster, out_table,
                                                            is_thematic)
                    latest_time = time.strftime('%Y-%m-%d %H:%M:%S')
                    count_diff = result[1]
                    e = 'N/A'

                except Exception, e:
                    # If it doesn't work, then don't change the "latest file" values for all of these

                    in_count = line['In Count']
                    count_diff = line['Count NULL']
                    latest_time = line['Latest Completion Time']
                    out_table = line['Output Table Path']

                write_line = line
                write_line['Output Table Shortname'] = out_table_shortname
                write_line['Output Table Path'] = out_table
                write_line['In Count'] = in_count
                write_line['Count NULL'] = count_diff
                write_line['Latest Execution Time'] = latest_time
                write_line['Latest Execution Error'] = e
                writer.writerow(write_line)

                arcpy.ResetEnvironments()

    shutil.copy(tempfile.name, control_file)
    os.remove(tempfile.name)


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
    # TODO: Switch it back to main
    test()
