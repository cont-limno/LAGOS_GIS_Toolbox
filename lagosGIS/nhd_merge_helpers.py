# filename: nhd_merge_helpers.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (NO ArcGIS Toolbox)

import os
import arcpy


def batch_add_merge_ids(nhd_parent_directory, overwrite=False):
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
            if filename in ['NHDWaterbody', 'NHDFlowline', 'NHDArea']:
                fc = os.path.join(dirpath, filename)
                fcs.append(fc)

    # For each fc in the list, calculate a new field. The two fields being concatenated into the new field are
    # a composite key in a naive merge of all NHD features (with full identicals removed).
    for fc in fcs:
        print("Adding new identifier all_merge_id to {}...".format(fc.split(nhd_parent_directory)[1]))
        if arcpy.ListFields(fc, "nhd_merge_id"):
            if overwrite:
                arcpy.DeleteField_management(fc, "nhd_merge_id")
            else:
                continue
        arcpy.AddField_management(fc, "nhd_merge_id", "TEXT", field_length=70)
        with arcpy.da.UpdateCursor(fc, ["nhd_merge_id", "Permanent_Identifier", "FDate"]) as cursor:
            for row in cursor:
                row[0] = '{}_{}'.format(row[1], str(row[2]))
                cursor.updateRow(row)


def batch_add_merge_ids2(nhd_parent_directory):
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
    arcpy.env.workspace = nhd_parent_directory
    all_gdbs = arcpy.ListWorkspaces("*")
    for gdb in all_gdbs:
        print(gdb)
        fcs.append(os.path.join(nhd_parent_directory, gdb, 'NHDWaterbody'))
        #fcs.append(os.path.join(nhd_parent_directory, gdb, 'NHDArea'))
        #fcs.append(os.path.join(nhd_parent_directory, gdb, 'NHDFlowline'))

    # For each fc in the list, calculate a new field. The two fields being concatenated into the new field are
    # a composite key in a naive merge of all NHD features (with full identicals removed).
    for fc in fcs:
        print("Adding new identifier all_merge_id to {}...".format(fc.split(nhd_parent_directory)[1]))
        try:
            arcpy.AddField_management(fc, "nhd_merge_id", "TEXT", field_length=70)
        except:
            pass
        with arcpy.da.UpdateCursor(fc, ['Permanent_Identifier', 'FDate', 'nhd_merge_id']) as cursor:
            for row in cursor:
                row[2] = '{}_{}'.format(row[0], str(row[1]))
                cursor.updateRow(row)


def deduplicate_nhd(in_feature_class_or_table, out_feature_class_or_table ='', unique_id ='Permanent_Identifier'):
    """
    Returns an single feature class for all NHD features with no duplicated identifiers in it.
    :param in_feature_class_or_table: A feature class resulting from merging features from NHD datasets staged by subregion.
    :param out_feature_class_or_table: Optional. The feature class which will be created.
    :param unique_id: Optional. The identifier that needs to be unique in the output.
    :return:
    """
    # SETUP
    if out_feature_class_or_table:
        arcpy.AddMessage("Copying initial features to output...")
        if arcpy.Describe(in_feature_class_or_table).dataType == "FeatureClass":
            arcpy.CopyFeatures_management(in_feature_class_or_table, out_feature_class_or_table)
        if arcpy.Describe(in_feature_class_or_table).dataType == "Table":
            arcpy.CopyRows_management(in_feature_class_or_table, out_feature_class_or_table)
    else:
        out_feature_class_or_table = in_feature_class_or_table

    # EXECUTE
    # Delete full identicals first--these come from overlaps in staged subregion data
    before_count = int(arcpy.GetCount_management(out_feature_class_or_table).getOutput(0))
    arcpy.AddMessage("Deleting full identicals...")
    # Check for full identicals on original *attribute fields*, excluding the one we specifically created to make them distinct
    # Also excluding object ID since that is obviously distinct
    excluded_fields = ['Shape', 'Shape_Length', 'Shape_Area', 'OBJECTID', 'nhd_merge_id']
    check_fields = [f.name for f in arcpy.ListFields(out_feature_class_or_table) if f.name not in excluded_fields]
    arcpy.DeleteIdentical_management(out_feature_class_or_table, check_fields)
    after_full_count = int(arcpy.GetCount_management(out_feature_class_or_table).getOutput(0))
    arcpy.AddMessage("{0} features were removed because they were full identicals to remaining features.".format(before_count - after_full_count))

    # Delete duplicated IDs by taking the most recent FDate--these come from NHD editing process somehow
    arcpy.AddMessage("Deleting older features with duplicated identifiers...")

    # Get a list of distinct IDs that have duplicates
    arcpy.Frequency_analysis(out_feature_class_or_table, "in_memory/freqtable", unique_id)
    arcpy.TableSelect_analysis("in_memory/freqtable", "in_memory/dupeslist", '''"FREQUENCY" > 1''')
    count_dupes = int(arcpy.GetCount_management("in_memory/dupeslist").getOutput(0))

    #If there are any duplicates, remove them by keeping the one with the latest FDate
    if count_dupes > 0:
        dupe_ids = [row[0] for row in arcpy.da.SearchCursor("in_memory/dupeslist", (unique_id))]
        dupe_filter = ''' "{}" = '{{}}' '''.format(unique_id)
        for id in dupe_ids:
            dates = [row[0] for row in arcpy.da.SearchCursor(out_feature_class_or_table, ["FDate"], dupe_filter.format(id))]
            with arcpy.da.UpdateCursor(out_feature_class_or_table, [unique_id, "FDate"], dupe_filter.format(id)) as cursor:
                for row in cursor:
                    if row[1] == max(dates):
                        pass
                    else:
                        cursor.deleteRow()
        after_both_count = int(arcpy.GetCount_management(out_feature_class_or_table).getOutput(0))
        arcpy.AddMessage("{0} features were removed because they were less recently edited than another feature with the same identifier.".format(after_full_count - after_both_count))

    arcpy.AddIndex_management(out_feature_class_or_table, "nhd_merge_id", "IDX_nhd_merge_id")
    arcpy.Delete_management("in_memory/freqtable")
    arcpy.Delete_management("in_memory/dupeslist")
