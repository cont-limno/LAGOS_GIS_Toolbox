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
        arcpy.AddField_management(fc, "nhd_merge_id", "TEXT", field_length = 70)
        arcpy.CalculateField_management(fc, "nhd_merge_id", '''!Permanent_Identifier! + '_' + str(!FDate!)''', "PYTHON")


def deduplicate_nhd(in_feature_class, out_feature_class = '', unique_id = 'Permanent_Identifier'):
    """
    Returns an single feature class for all NHD features with no duplicated identifiers in it.
    :param in_feature_class: A feature class resulting from merging features from NHD datasets staged by subregion.
    :param out_feature_class: Optional. The feature class which will be created.
    :param unique_id: Optional. The identifier that needs to be unique in the output.
    :return:
    """
    # SETUP
    arcpy.env.scratchWorkspace = os.getenv("TEMP")
    temp_dupes = arcpy.CreateUniqueName("temp_dupes", arcpy.env.scratchGDB)
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
    result = arcpy.FindIdentical_management(out_feature_class, temp_dupes, unique_id, output_record_option = "ONLY_DUPLICATES")
    lyr = arcpy.MakeFeatureLayer_management(out_feature_class, "join_lyr")
    arcpy.AddJoin_management(lyr, "OBJECTID", result.getOutput(0), "IN_FID", "KEEP_COMMON")
    dupe_ids = list(set([row[0] for row in arcpy.da.SearchCursor(out_feature_class, [unique_id])]))
    arcpy.RemoveJoin_management(out_feature_class)
    dupe_filter = ''' unique_id == '{}' '''
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

    # CLEANUP
    arcpy.Delete_management(temp_dupes)