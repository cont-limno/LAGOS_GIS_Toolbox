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

    #TODO: The validation script should check the control file schema
    #TODO: Upper case protect
    with open(control_file) as csv_file:
        reader = csv.DictReader(csv_file)
        field_names = reader.fieldnames
        lines = [line for line in reader]


    linenum = 0
    sum_problem_count = 0
    line_problem_count = 0
    zones_missing_ids = []
    zones = []
    rasters = []
    jobnum_set = set()
    combos_set = set()


    for line in lines:
        linenum += 1
        zone = line['Zone Path']
        raster = line['Raster Path']
        combo = zone + raster
        if combo in combos_set:
            print("ERROR: Duplicate zone/raster combination. Duplicate is found at line {}".format(linenum))
            line_problem_count += 1
        else:
            combos_set.add(combo)
        jobnum = line['Jobnum']

        if not jobnum:
            print("ERROR: Add job number to line {}".format(linenum))
            line_problem_count += 1
        else:
            if filter and (jobnum > filter[1] or jobnum < filter[0]):
                continue
            if jobnum in jobnum_set:
                print("ERROR: Duplicate job number. First duplication is at line {}".format(linenum))
            else:
                jobnum_set.add(jobnum)

        # Check the zones fc
        if zone not in zones:
            print("zone" + jobnum)
            if arcpy.Exists(zone):
                if not arcpy.ListFields(zone, 'ZoneID') and zone not in zones_missing_ids:
                    zones_missing_ids.append(zone)
                    line_problem_count += 1
                proj = arcpy.Describe(zone).spatialReference.factoryCode
                if proj not in [102039, 5070]:
                    print("ERROR: Zone projection is not USGS Albers for line {}".format(linenum))
                    line_problem_count += 1

            else:
                print("ERROR: Zone feature class path not valid for line {}".format(linenum))
                line_problem_count += 1

        # Check the raster
        if raster not in rasters:
            print("raster" + jobnum)
            if arcpy.Exists(raster):
                if int(arcpy.GetRasterProperties_management(raster, "VALUETYPE").getOutput(0)) < 5 and line['Is Thematic'] <> 'Y':
                    print("WARNING: Check thematic flag for line {}".format(linenum))
                    # no addition to line_problem_count
                extent = arcpy.Describe(raster).extent
                if extent.YMax < 250000:
                    raster_basename = os.path.basename(raster)
                    print("ERROR: Raster does not overlap zones. Check the projection of {} (line {}).".format(
                        raster_basename, linenum))
                    line_problem_count += 1
            else:
                print("ERROR: Raster path not valid for line {}".format(linenum))
                line_problem_count += 1

        zones.append(zone)
        rasters.append(raster)
        if line_problem_count > 0:
            sum_problem_count += line_problem_count
        else:
            lines[linenum-1]['Is Valid'] = 'Y'
            tempfile = NamedTemporaryFile(delete=False)
            with tempfile:
                writer = csv.DictWriter(tempfile, field_names)
                writer.writeheader()
                writer.writerows(lines)
            shutil.copy(tempfile.name, control_file)
            os.remove(tempfile.name)


    for z in zones_missing_ids:
        print("ERROR: {} is missing a ZoneID field").format(z)
    time.sleep(1)  # keep other messages from interrupting list

    if sum_problem_count == 0:
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
    with open(control_file, 'rb') as csv_file:
        reader1 = csv.DictReader(csv_file)
        field_names = reader1.fieldnames
        lines_mem = [line for line in reader1]

    line_n = 0
    for line in lines_mem:
        jobnum = int(line['Jobnum'])
        if filter and (jobnum > int(filter[1]) or jobnum < int(filter[0])):
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
            continue

        else:
            if force_rerun == 'Y':
                arcpy.env.overwriteOutput = True
            print("Creating {0}...Start Time {1}".format(out_table, time.strftime('%Y-%m-%d %H:%M:%S')))
            in_count = int(arcpy.GetCount_management(zone_fc).getOutput(0))

            try:
                result = zonal_tabarea.stats_area_table(zone_fc, zone_field, in_value_raster, out_table,
                                                        is_thematic)
                latest_time = time.strftime('%Y-%m-%d %H:%M:%S')
                count_diff = result[1]
                e = 'N/A'

            except Exception, e:
                # If it doesn't work, then don't change the "latest file" values for all of these
                print(e)
                in_count = line['In Count']
                count_diff = line['Count NULL']
                latest_time = line['Latest Execution Time']
                out_table = line['Output Table Path']

            write_line = line
            write_line['Output Table Shortname'] = out_table_shortname
            write_line['Output Table Path'] = out_table
            write_line['In Count'] = in_count
            write_line['Count NULL'] = count_diff
            write_line['Latest Execution Time'] = latest_time
            write_line['Latest Execution Error'] = e

            # Write out all lines each time so that batch script interruptions aren't a big issue
            # Keeps lines_mem up-to-date in memory as well
            lines_mem[line_n] = write_line

            tempfile = NamedTemporaryFile(delete=False)
            with tempfile:
                writer = csv.DictWriter(tempfile, field_names)
                writer.writeheader()
                writer.writerows(lines_mem)
            shutil.copy(tempfile.name, control_file)
            os.remove(tempfile.name)

            arcpy.ResetEnvironments()
            line_n += 1

def main():
    CONTROL_FILE = ''
    OUTPUT_GEODATABASE = ''
    FILTER = ''
    batch_run(CONTROL_FILE, OUTPUT_GEODATABASE, FILTER)

def test():
    CONTROL_FILE = r"C:\Users\smithn78\Documents\Nicole temp\test_batch_run.csv"
    OUTPUT_GEODATABASE = r'C:\Users\smithn78\Documents\ArcGIS\Default.gdb'
    FILTER = (1,1)
    #batch_run(CONTROL_FILE, OUTPUT_GEODATABASE, FILTER, False)
    result = validate_control_file(CONTROL_FILE)
    print("Test complete. Result = {}".format(result))

    #test change

if __name__ == '__main__':
    main()
