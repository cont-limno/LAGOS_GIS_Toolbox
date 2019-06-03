__all__ = ["lake_connectivity_classification",
           "zonal_attribution_of_raster_data",
           "efficient_merge", "export_to_csv",
           "upstream_lakes",
           "spatialize_lakes",
           "georeference_lakes",
           "multi_convert_to_raster",
           "lake_from_to",
           "polygons_in_zones",
           "lakes_in_zones",
           "aggregate_watersheds_NE",
           "aggregate_watersheds_US",
           "subset_overlapping_zones"]

import os
import arcpy
from LakeConnectivity import full_classify as lake_connectivity_classification
from zonal_tabarea import handle_overlaps as zonal_attribution_of_raster_data
from color_polygons import colorPolygons as subset_overlapping_zones
from Export2CSV import TableToCSV as export_to_csv
from upstream_lakes import upstream_lakes
from georeference import spatialize_lakes
from georeference import georeference_lakes
from multi_convert_to_raster import multi_convert_to_raster
from lake_from_to import lake_from_to
from polygons_in_zones import polygons_in_zones
from lakes_in_zones2 import lakes_in_zones
from interlake2 import aggregate_watersheds as aggregate_watersheds_NE
# from nhdplushr_tools import aggregate_watersheds2 as aggregate_watersheds_US

LAGOS_FCODE_LIST = (39000,39004,39009,39010,39011,39012,43600,43613,43615,43617,43618,43619,43621)
def efficient_merge(feature_class_or_table_list, output_fc, filter =''):
    fc_count = len(feature_class_or_table_list)
    all_exist_test = all(arcpy.Exists(fct) for fct in feature_class_or_table_list)

    # EXECUTE
    # Start with FC containing largest extent to prevent spatial grid errors
    description = arcpy.Describe(feature_class_or_table_list[0])
    if description.dataType == "FeatureClass":
        descriptions = [arcpy.Describe(fc).extent for fc in feature_class_or_table_list]
        fc_areas = [int(d.XMax-d.XMin) * int(d.YMax-d.YMin) for d in descriptions]
        index = [i for i, x in enumerate(fc_areas) if x == max(fc_areas)]
        first_fc = feature_class_or_table_list[index[0]]
        feature_class_or_table_list.remove(first_fc)
    else:
        first_fc = feature_class_or_table_list.pop(0)


    # This is a fast and stable merge method for this number of features compared to arcpy Merge
    if all_exist_test:
        print("Beginning merge of {} feature classes, copying first feature class to output...".format(fc_count))
        if description.dataType == "FeatureClass":
            arcpy.Select_analysis(first_fc, output_fc, filter)
        else:
            arcpy.TableSelect_analysis(first_fc, output_fc, filter)
        arcpy.SetLogHistory = False  # speeds up iterative updates, won't write to geoprocessing for every step
        cursor_fields = ["*"]
        if description.dataType == "FeatureClass":
            cursor_fields.append('SHAPE@')
        insertRows = arcpy.da.InsertCursor(output_fc, cursor_fields)

        for fc in feature_class_or_table_list:
            searchRows = arcpy.da.SearchCursor(fc, cursor_fields, filter)
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
            arcpy.AddIndex_management(output_fc, 'nhd_merge_id', 'IDX_nhd_merge_id')
        except:
           arcpy.AddWarning('Could not build Permanent_Identifier index because there is no such field.')
        return arcpy.Describe(output_fc).catalogPath

    else:
        print("ERROR: One or more feature class paths is not valid. Merged feature class not created.")
        return False

def list_shared_words(string1, string2, exclude_lake_words = True ):
    """
    Return a list of common words in two strings formatted as normal text (with spaces in between words).
    :param string1: String to compare
    :param string2: String to compare
    :param exclusion_set: Excludes the words 'LAKE' and 'POND' by default. False allows these words to be returned in
    the result
    :return: A list of words.
    """
    EXCLUSION_SET = set(['LAKE', 'POND', 'RESERVOIR', 'DAM'])
    if not (isinstance(string1, basestring) and isinstance(string2, basestring)):
        raise TypeError("inputs must each be a string")

    words1 = set(string1.upper().split())
    words2 = set(string2.upper().split())
    if exclude_lake_words:
        words1 = words1.difference(EXCLUSION_SET)
        words2 = words2.difference(EXCLUSION_SET)
    return ' '.join(list(words1.intersection(words2)))

def select_fields(feature_class_or_table, output, field_list, convert_to_table = False):
    '''
    Select outputs a dataset with only the user-selected fields, the OID, and the geometry, if applicable.
    :param feature_class_or_table: The feature class or table to select from.
    :param output: The path to the output feature class or table.
    :param field_list: A list of fields to be selected.
    :param convert_to_table: Optional, boolean. Default True. Whether to return the output as the Table dataset type.
    :return: ArcGIS Result object.
    '''
    input_type = arcpy.Describe(feature_class_or_table).dataType
    dir_name = os.path.dirname(output)
    if dir_name:
        out_workspace = dir_name
    else:
        out_workspace = arcpy.env.workspace
    out_basename = os.path.basename(output)

    field_mapping = arcpy.FieldMappings()
    for f in field_list:
        map = arcpy.FieldMap()
        map.addInputField(feature_class_or_table, f)
        field_mapping.addFieldMap(map)

    if not convert_to_table and input_type == "FeatureClass":
        result = arcpy.FeatureClassToFeatureClass_conversion(feature_class_or_table, out_workspace, out_basename, '#', field_mapping)
    else:
        if input_type == "FeatureClass":
            feature_class_or_table = arcpy.CopyRows_management(feature_class_or_table, 'in_memory/temp_copy')
        result = arcpy.TableToTable_conversion(feature_class_or_table, out_workspace, out_basename, '#', field_mapping)
        arcpy.Delete_management('in_memory/temp_copy')

    return result
