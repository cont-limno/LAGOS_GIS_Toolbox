#!/usr/bin/env python
import os, time
import arcpy
"""
This module contains custom functions necessary to reproduce the research the Lakes in the US paper.
"""

def batch_add_merge_ids(nhd_parent_directory):
    """
    Adds a new id field called nhd_merge_id to all feature classes containing the identifier "Permanent_Identifier"
    in all NHD geodatabases in the parent directory provided. The resulting field can be used to link multiple
    geoprocessing outputs from NHD datasets staged by subregion to the source features (merged or original) without
    ID conflicts. Outputs will also need a merge rule to be safely combined, see nhd_gp_output_merge.

    :param nhd_parent_directory: The directory containing all (unzipped) NHD subregion geodatabases.
    :return: None
    """
    # Find all fcs containing a field called "Permanent_Identifier"
    print("Finding feature classes containing Permanent_Identifier...")
    fcs = []
    for dirpath, dirnames, filenames in arcpy.da.Walk(nhd_parent_directory, datatype="FeatureClass"):
        for filename in filenames:
            fc = os.path.join(dirpath, filename)
            # Why can't it be easier to test for a field?
            perm_id_search_result = arcpy.ListFields(fc, "Permanent_Identifier")
            if perm_id_search_result:
                perm_id_field = perm_id_search_result[0]
                fdate_search_result = arcpy.ListFields(fc, "FDate")
                if fdate_search_result:
                    fdate_field = fdate_search_result[0]
                    fcs.append(fc)

    # For each fc in the list, calculate a new field. The two fields being concatenated into the new field are
    # a composite key in a naive merge of all NHD features (with full identicals removed).
    for fc in fcs:
        print("Adding new identifier all_merge_id to {}...".format(fc.split(nhd_parent_directory)[1]))
        if arcpy.ListFields(fc, "nhd_merge_id"):
            arcpy.DeleteField_management(fc, "nhd_merge_id")
        arcpy.AddField_management(fc, "nhd_merge_id", "TEXT", field_length=70)
        arcpy.CalculateField_management(fc, "nhd_merge_id", '''!Permanent_Identifier! + '_' + str(!FDate!)''', "PYTHON")

def efficient_merge(feature_class_list, output_fc, filter =''):
    fc_count = len(feature_class_list)
    all_exist_test = all(arcpy.Exists(fc) for fc in feature_class_list)

    # EXECUTE
    # Start with FC containing largest extent to prevent spatial grid errors
    descriptions = [arcpy.Describe(fc).extent for fc in feature_class_list]
    fc_areas = [int(d.XMax-d.XMin) * int(d.YMax-d.YMin) for d in descriptions]
    index = [i for i, x in enumerate(fc_areas) if x == max(fc_areas)]
    first_fc = feature_class_list[index[0]]
    indexes = arcpy.ListIndexes(first_fc)
    feature_class_list.remove(first_fc)

    # This is a fast and stable merge method for this number of features compared to arcpy Merge
    if all_exist_test:
        print("Beginning merge of {} feature classes, copying first feature class to output...".format(fc_count))
        arcpy.Select_analysis(first_fc, output_fc, filter)
        arcpy.SetLogHistory = False  # speeds up iterative updates, won't write to geoprocessing for every step
        insertRows = arcpy.da.InsertCursor(output_fc, ["SHAPE@", "*"])

        for fc in feature_class_list:
            searchRows = arcpy.da.SearchCursor(fc, ["SHAPE@", "*"], filter)
            counter = 0
            for searchRow in searchRows:
                insertRows.insertRow(searchRow)
                counter +=1
            del searchRow, searchRows
            print("Merged {0} features from {1}".format(counter, fc))
        del insertRows
        arcpy.SetLogHistory = True

        # Rebuild indexes
        try:
            arcpy.AddIndex_management(output_fc, 'Permanent_Identifier', 'IDX_Permanent_Identifier')
        except:
           arcpy.AddWarning('Could not build Permanent_Identifier index because there is no such field.')

    else:
        print("ERROR: One or more feature class paths is not valid. Merged feature class not created.")




def deduplicate_nhd(in_feature_class, out_feature_class = '', unique_id = 'Permanent_Identifier'):
    """
    Returns an single feature class for all NHD features with no duplicated identifiers in it.
    :param in_feature_class: A feature class resulting from merging features from NHD datasets staged by subregion.
    :param out_feature_class: Optional. The feature class which will be created.
    :param unique_id: Optional. The identifier that needs to be unique in the output.
    :return:
    """
    # SETUP
    if out_feature_class:
        arcpy.AddMessage("Copying initial features to output...")
        arcpy.CopyFeatures_management(in_feature_class, out_feature_class)
    else:
        out_feature_class = in_feature_class

    # EXECUTE
    # Delete full identicals first--these come from overlaps in staged subregion data
    before_count = int(arcpy.GetCount_management(out_feature_class).getOutput(0))
    arcpy.AddMessage("Deleting full identicals...")
    # Check for full identicals on original *attribute fields*, excluding the one we specifically created to make them distinct
    # Also excluding object ID since that is obviously distinct
    excluded_fields = ['Shape', 'Shape_Length', 'Shape_Area', 'OBJECTID', 'nhd_merge_id']
    check_fields = [f.name for f in arcpy.ListFields(out_feature_class) if f.name not in excluded_fields]
    arcpy.DeleteIdentical_management(out_feature_class, check_fields)
    after_full_count = int(arcpy.GetCount_management(out_feature_class).getOutput(0))
    arcpy.AddMessage("{0} features were removed because they were full identicals to remaining features.".format(before_count - after_full_count))

    # Delete duplicated IDs by taking the most recent FDate--these come from NHD editing process somehow
    arcpy.AddMessage("Deleting older features with duplicated identifiers...")

    # Get a list of distinct IDs that have duplicates
    arcpy.Frequency_analysis(out_feature_class, "in_memory/freqtable", unique_id)
    arcpy.TableSelect_analysis("in_memory/freqtable", "in_memory/dupeslist", '''"FREQUENCY" > 1''')
    count_dupes = int(arcpy.GetCount_management("in_memory/dupeslist").getOutput(0))

    #If there are any duplicates, remove them by keeping the one with the latest FDate
    if count_dupes > 0:
        dupe_ids = [row[0] for row in arcpy.da.SearchCursor("in_memory/dupeslist", (unique_id))]
        dupe_filter = ''' "{}" = '{{}}' '''.format(unique_id)
        for id in dupe_ids:
            dates = [row[0] for row in arcpy.da.SearchCursor(out_feature_class, ["FDate"], dupe_filter.format(id))]
            with arcpy.da.UpdateCursor(out_feature_class, [unique_id, "FDate"], dupe_filter.format(id)) as cursor:
                for row in cursor:
                    if row[1] == max(dates):
                        pass
                    else:
                        cursor.deleteRow()
        after_both_count = int(arcpy.GetCount_management(out_feature_class).getOutput(0))
        arcpy.AddMessage("{0} features were removed because they were less recently edited than another feature with the same identifier.".format(after_full_count - after_both_count))

    arcpy.AddIndex_management(out_feature_class, "nhd_merge_id", "IDX_nhd_merge_id", "UNIQUE")
    arcpy.Delete_management("in_memory/freqtable")
    arcpy.Delete_management("in_memory/dupeslist")
