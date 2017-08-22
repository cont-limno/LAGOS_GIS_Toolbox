__all__ = ["lake_connectivity_classification", "zonal_attribution_of_raster_data", "efficient_merge", "export_to_csv"]

import arcpy
from LakeConnectivity import full_classify as lake_connectivity_classification
from zonal_tabarea import handle_overlaps as zonal_attribution_of_raster_data
from Export2CSV import TableToCSV as export_to_csv

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