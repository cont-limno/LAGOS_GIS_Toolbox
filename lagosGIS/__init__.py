__all__ = ["lake_connectivity_classification", "zonal_attribution_of_raster_data", "efficient_merge", "export_to_csv", "upstream_lakes"]

import arcpy
from LakeConnectivity import full_classify as lake_connectivity_classification
from zonal_tabarea import handle_overlaps as zonal_attribution_of_raster_data
from Export2CSV import TableToCSV as export_to_csv
from upstream_lakes import upstream_lakes


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
