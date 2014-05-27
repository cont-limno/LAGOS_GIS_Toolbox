import os
import arcpy
from arcpy import env


def check_unique_id(polygon_fc, candidate_id, table_workspace = 'in_memory'):
    """Checks if the id you think is unique actually has no duplicates. Returns
    True if ID is unique, False if there are duplicates.
    If there are duplicates, remove them manually and use this function again
    when you are done to verify success."""
    frequency_table = os.path.join(table_workspace, os.path.splitext(os.path.basename(polygon_fc))[0] + '_freqtable')
    arcpy.Frequency_analysis(polygon_fc, frequency_table, candidate_id)
    fields = [candidate_id, 'FREQUENCY']
    with arcpy.da.SearchCursor(frequency_table, fields) as cursor:
        print_rows = [fields[0].ljust(80) + fields[1]]
        count = 0
        for row in cursor:
            if row[1] > 1:
                count += 1
                printable = row[0].ljust(80) + str(row[1])
                print_rows.append(printable)
    if count > 0:
        print("WARNING: %s is NOT unique for feature class %s." % (candidate_id, polygon_fc))
        for line in print_rows:
            print(line)
        return False
    else:
        print("Success! You can use the id %s for feature class %s" % (candidate_id, polygon_fc))
        return True
def check_geo_overlap(polygon_fc, unique_id, table_workspace = 'in_memory', acceptable_overlap = 0):
    """Prints out a list of overlapping areas between polygons, if any.
    Returns a value of true or false indicating if there were areas of concern.

    polygon_fc: a polygon feature class path

    unique_id: the primary key or field that uniquely identifies this feature.
    If there is doubt about the uniqueness, use the check_unique_id function first.

    table_workspace: Default is "in_memory". Choose an output geodatabase.

    acceptable_overlap: the upper limit of the amount of overlap that can be
    considered negligible, in map units. For instance, 1 sq. m of overlap is
    not a problem for many applications"""
    neighbor_table = os.path.join(table_workspace, os.path.splitext(os.path.basename(polygon_fc))[0] + '_neighbortable')
    arcpy.PolygonNeighbors_analysis(polygon_fc, neighbor_table, unique_id,
        'AREA_OVERLAP', 'NO_BOTH_SIDES')
    fields = ['src_' + unique_id, 'nbr_' + unique_id, 'AREA']
    with arcpy.da.SearchCursor(neighbor_table, fields) as cursor:
        print_rows = [fields[0].ljust(80) + fields[1].ljust(80) + fields[2]]
        count = 0
        for row in cursor:
            if row[2] > acceptable_overlap:
                count += 1
                printable = row[0].ljust(80) + row[1].ljust(80) + str(round(row[2],1))
                print_rows.append(printable)
    if count > 0:
        print("WARNING: The following areas overlap in feature class %s." % polygon_fc)
        for line in print_rows:
            print(line)
        return True
    else:
        print("Success! There were no areas of overlap in feature class %s." % polygon_fc)
        return False

#----------------------------------------------------------------------------------------------
# Name:     FDates
# Purpose:  Merging NHD subregions together produces a feature class with duplicate
#           features.  Reasons for duplicates are features that cross subregion boundaries and
#           features that were updated in one "snapshot" NHD subregion. Need to make sure we
#           remove duplicates, and remove oldest feature in the process
# Reqs:     Merged NHD waterbody feature class located at the inPath below
# Author:   Ed Bissell, updated by Nicole Smith 03/13/2014
# Created:  7/13/2012
#----------------------------------------------------------------------------------------------

def remove_nhd_duplicates(in_fc, unique_id, out_fc):
    """This function will resolve identifier duplications from any NHD-based
    layer. Use when you need to be sure the identifier values are unique. Some
    processing chains will result in duplications where edits to the feature
    are apparently saved twice. This function will save the feature with the
    newest time stamp and drop all the rest of the records with the same value
    in the field you specify as unique_id. If there are no duplications, the
    function will exit safely.

    in_fc: the feature class that might have duplicates that is derived from an
    NHD (National Hydrological Dataset) layer such as NHDWaterbodies or
    NHDFlowlines

    unique_id: The field you want to use as a primary key, or unique identifier
    of features. Any value appearing more than once in this input will be
    resolved in the output so that it only appears once. With the NHD, this will
    usually be the 'Permanent_Identifier' column, which you may have already
    renamed.
    be the 'Permanent_Identifier' column

    out_fc: the desired path for the output feature class"""
    ws = 'C:/GISData/Scratch/fake_memory.gdb'
    env.workspace = ws

    print("Creating frequency table...")
    arcpy.Frequency_analysis(in_fc, "freqtable", unique_id)

    # Pick out just the records we need to work with, the rest will be
    # saved to the output and we will merge in the results from our working
    # set later
    arcpy.MakeFeatureLayer_management(in_fc, "fc_lyr")
    arcpy.AddJoin_management("fc_lyr", unique_id, "freqtable", unique_id)
    arcpy.Select_analysis("fc_lyr", out_fc, '''"FREQUENCY" = 1''')
    arcpy.Select_analysis("fc_lyr", "fc_temp", '''"FREQUENCY" > 1''')
    arcpy.RemoveJoin_management("fc_lyr")

    arcpy.AddField_management("fc_temp", "NewestFDate", "SHORT")
    arcpy.CalculateField_management("fc_temp", "NewestFDate", 1, 'PYTHON')

    arcpy.TableSelect_analysis("freqtable", "dupetable", '''"FREQUENCY" > 1''')

    count_dupes = int(arcpy.GetCount_management("dupetable").getOutput(0))

    if count_dupes > 0:
        print("Number of records in duplicates table is %d" % count_dupes)

        # Make a list of truly unique ids for use in selecting groups of identical ids
        select_ids = [row[0] for row in arcpy.da.SearchCursor("dupetable", (unique_id))]

        # for each id select its group of duplicates
        for s_id in select_ids:

            whereClause =  ''' "%s" = '%s' ''' % (unique_id, s_id)

            # update values to 0, we will change only one to 1 later
            # and get a list of all the dates
            dates = [row[0] for row in arcpy.da.SearchCursor("fc_temp", ("FDate"), whereClause)]

            print("ID group %s" % s_id)
            print("Date object values: %s" % dates)
            print("Newest date: %s\n" % max(dates))

            # just using "Fdate" = max(dates) logic DOES NOT WORK CORRECTLY
            # sometimes more than one record with max date but
            # the following allows us to use "NewestFDate" = 1 later to
            # select ONLY ONE to keep
            with arcpy.da.UpdateCursor("fc_temp", ("FDate", "NewestFDate"), whereClause) as cursor:
                i = 1
                for row in cursor:
                    if row[0] == max(dates):
                        row[1] = i
                        i += 1
                    else:
                        row[1] = 0
                    cursor.updateRow(row)

        # create a new, distinct output rather than updating table in place
        arcpy.Select_analysis("fc_temp", "newest_only", ''' "NewestFDate" = 1 ''')
        arcpy.DeleteField_management("newest_only", "NewestFDate")
        arcpy.Merge_management("newest_only", out_fc)

        for intermediate in ["freqtable", "dupetable", "fc_temp"]:
            arcpy.Delete_management(intermediate)

    else:
        print("There were no duplicates.")

# to remove geographic duplicates: for each pair, if the overlapping area exceeds
# 90% of the area of the source lake (i.e. they are almost certainly two copies
# of the same lake and not some other type of overlap), look up the neighbor lake
# and add the older of the two to a drop list, then run the drop all at once

def remove_geographic_doubles(polygon_fc, out_fc, unique_id, percent_overlap_allowed = 10, keep_fc = '', keep_field = ''):
    neighbor_table = 'in_memory/neighbortable'
    print('Calculating neighbor table...')
    arcpy.PolygonNeighbors_analysis(polygon_fc, neighbor_table, unique_id,
        'AREA_OVERLAP', 'NO_BOTH_SIDES')

    # need these to avoid some naming problems that arise from trying to
    # do this directly
    src_field = arcpy.ListFields(neighbor_table, 'src*')[0].name
    nbr_field = arcpy.ListFields(neighbor_table, 'nbr*')[0].name

    arcpy.CopyFeatures_management(polygon_fc, 'in_memory/fc')
    fdate_field = arcpy.ListFields('in_memory/fc', '*FDate*')[0].name
    print('Joining neighbor table to feature class...')
    arcpy.JoinField_management('in_memory/fc', unique_id, neighbor_table,
                            src_field)

    cursor_fields = ['AREA', 'SHAPE@AREA', unique_id, nbr_field, fdate_field]
##    print([f.name for f in arcpy.ListFields('in_memory/fc')])

    if keep_fc:
        keep_ids = [row[0] for row in arcpy.da.SearchCursor(keep_fc, keep_field)]
    else:
        keep_ids = []

    with arcpy.da.SearchCursor('in_memory/fc', cursor_fields) as cursor:
        for row in cursor:

            # If this row represents a duplicate-type overlap
            if row[0] >= row[1] * (100 - percent_overlap_allowed)/100:
                src_value = row[2]
                nbr_value = row[3]
##                print("testing. pair: %s and %s" % (src_value, nbr_value))

                # Then lookup both rows in the overlap and delete the one with
                # the oldest FDate
                where_clause = '''"%s" = '%s' OR "%s" = '%s' ''' % (unique_id, src_value, unique_id, nbr_value)
                dates = [row[4] for row in arcpy.da.SearchCursor('in_memory/fc', cursor_fields, where_clause)]
##                print("testing. dates %s and %s not in order" % (dates[0], dates[1]))
                with arcpy.da.UpdateCursor('in_memory/fc', cursor_fields, where_clause) as c:
                    for r in c:
                        if r[4] == min(dates) and r[4] == max(dates):
                            print("PROBLEM! Same date. Resolve pair %s, %s manually." % (ids[0], ids[1]))
                        if r[4] == min(dates) and r[4] != max(dates):
                            if r[4] not in keep_ids:
                                print("%s has the older date (%s) and will be removed." % (r[2], r[4]))
##                                c.deleteRow()
                            if r[4] in keep_ids:
                                print("You're going to have to write this condition...")
                        else:
                            continue
            else:
                continue
    for drop_field in [src_field, nbr_field, 'AREA']:
        arcpy.DeleteField_management('in_memory/fc', drop_field)
    arcpy.CopyFeatures_management('in_memory/fc', out_fc)
    for item in [neighbor_table, 'in_memory/fc']:
        arcpy.Delete_management(item)