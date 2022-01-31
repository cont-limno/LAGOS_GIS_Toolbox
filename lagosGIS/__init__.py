__all__ = ["lake_connectivity_classification",
           "upstream_lakes",
           "locate_lake_outlets",
           "locate_lake_inlets",
           "aggregate_watersheds",
           "calc_watershed_subtype",
           "calc_watershed_equality",

           "point_density_in_zones",
           "line_density_in_zones",
           "polygon_density_in_zones",
           "stream_density",
           "lake_density",

           "flatten_overlaps",
           "rasterize_zones",
           "zonal_summary_of_raster_data",
           "zonal_summary_of_classed_polygons",
           "point_attribution_of_raster_data",
           "summarize_raster_for_all_zones",

           "spatialize_lakes",
           "georeference_lakes",

           "export_to_csv",
            "zone_prep"
    ]

import os
import arcpy
import tempfile
from lake_connectivity_classification import classify as lake_connectivity_classification
from upstream_lakes import count as upstream_lakes
from locate_lake_outlets import locate_lake_outlets
from locate_lake_inlets import locate_lake_inlets
from watershed_delineation.aggregate_watersheds import aggregate_watersheds as aggregate_watersheds
from watershed_delineation.postprocess_watersheds import calc_watershed_subtype
from watershed_delineation.postprocess_watersheds import calc_watershed_equality

from point_density_in_zones import calc as point_density_in_zones
from line_density_in_zones import calc as line_density_in_zones
from polygon_density_in_zones import calc as polygon_density_in_zones
from stream_density import calc_all as stream_density
from lake_density import calc_all as lake_density

from flatten_overlapping_zones import flatten as flatten_overlaps
from rasterize_zones import rasterize as rasterize_zones
from zonal_summary_of_raster_data import calc as zonal_summary_of_raster_data
from summarize_raster_for_all_zones import summarize as summarize_raster_for_all_zones

from zonal_summary_of_classed_polygons import summarize as zonal_summary_of_classed_polygons
from point_attribution_of_raster_data import attribution as point_attribution_of_raster_data

from georeference import spatialize_lakes
from georeference import georeference_lakes

from export_to_csv import export as export_to_csv
import zone_prep


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
        print("Beginning merge of {} feature classes, copying first feature class {} to output...".format(fc_count, first_fc))
        if description.dataType == "FeatureClass":
            arcpy.Select_analysis(first_fc, output_fc, filter)
        else:
            arcpy.TableSelect_analysis(first_fc, output_fc, filter)
        arcpy.SetLogHistory = False  # speeds up iterative updates, won't write to geoprocessing for every step
        cursor_fields = list(arcpy.da.SearchCursor(output_fc, ['*']).fields)
        if description.dataType == "FeatureClass":
            cursor_fields.append('SHAPE@')
        insertRows = arcpy.da.InsertCursor(output_fc, cursor_fields)

        for fc in feature_class_or_table_list:
            counter = 0
            searchRows = arcpy.da.SearchCursor(fc, cursor_fields, filter)
            for searchRow in searchRows:
                insertRows.insertRow(searchRow)
                counter +=1
            try:
                del searchRow, searchRows
            except:
                print("Merged NO features from {}; filter eliminated all features".format(fc))
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
    :param convert_to_table: Optional, boolean. Default False. Whether to return the output as the Table dataset type.
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


def multi_msg(message):
    """Prints given string message no matter where script is executed: in Python
    interpreter and ArcGIS geoprocessing dialog using
    print statement, also ArcGIS Results window (for background processing) or geoprocessing dialog using
    arcpy.AddMessage"""
    print(message)
    arcpy.AddMessage(message)


def merge_many(merge_list, out_fc, group_size = 20):
    """arcpy merge a list without blowing up your system
        this can be slow, but is usually better than the alternative
        if there are more than x (usually 20) files to merge, merge them in
        groups of 20 at a time to speed it up some"""
    if len(merge_list) > group_size:
        partitions = 1 + len(merge_list) // (group_size)
        multi_msg("Merging partition 1 of %s" % partitions)
        arcpy.Merge_management(merge_list[:group_size], out_fc)
        for n in range(2, partitions+1):
            multi_msg("Merging partition %s of %s" % (n, partitions))
            arcpy.Append_management(merge_list[group_size*(n-1):group_size*n], out_fc)
    else:
        arcpy.Merge_management(merge_list, out_fc)


def rename_field(inTable, oldFieldName, newFieldName, deleteOld = False):
    import arcpy
    old_field = arcpy.ListFields(inTable, oldFieldName)
    arcpy.AddField_management(inTable, newFieldName, old_field[0].type, field_length = old_field[0].length)
    arcpy.CalculateField_management(inTable, newFieldName,'!%s!' % oldFieldName, "PYTHON")
    if deleteOld == True:
        arcpy.DeleteField_management(inTable, oldFieldName)


def one_in_one_out(tool_table, zone_fc, zone_field, output_table):
    """ Occasionally, ArcGIS tools we use do not produce an output record for
    every input feature. This function is used in the toolbox whenever we need
    to correct this problem, and should be called at the end of the script to
    create the final output.
    tool_table: the intermediate table with missing features
    zone_fc: the feature class with the zones
    zone_field: the field uniquely identifying each feature that was used in
    the creation of tool_table. Because this function is called within our
    scripts, the zone_field should always be the same in tool_table and
    extent_fc
    output_table: the final output table
    """
    # get list of zones that need nulls inserted
    original_zones = {r[0] for r in arcpy.da.SearchCursor(zone_fc, zone_field)}
    null_zones = original_zones.difference({r[0] for r in arcpy.da.SearchCursor(tool_table, zone_field)})

    # get list of fields from table that can be inserted
    editable_fields = [f.name for f in arcpy.ListFields(tool_table) if f.editable]
    editable_fields.remove(zone_field)

    # insert a null row for every ID we identified
    iCursor = arcpy.da.InsertCursor(tool_table, [zone_field] + editable_fields)
    for zone_id in null_zones:
        new_row = [zone_id] + [None]*len(editable_fields)
        iCursor.insertRow(new_row)
    del iCursor

    # copy to output
    output_table = arcpy.CopyRows_management(tool_table, output_table)
    return output_table


def redefine_nulls(in_table, in_fields, out_values):
    """Sometimes, when a zone has nothing in it, it gets an output value of
    Null/NoData/None that we need to change to either a custom NA flag, or 0.
    in_table: the table that needs updating. It will be changed in place.
    in_fields: list of fields with null values that need updating
    out_values: a list the same length as in_fields, with the value to replace
    Null/NoData/None with.
    """
    arcpy.MakeTableView_management(in_table, 'table')
    for f, v in zip(in_fields, out_values):
        null_expr = '''"{0}" is null'''.format(f)
        arcpy.SelectLayerByAttribute_management('table', 'NEW_SELECTION', null_expr)
        calc_expr = """'{0}'""".format(v)
        arcpy.CalculateField_management('table', f, calc_expr, 'PYTHON')
    arcpy.Delete_management('table')


def resolution_comparison(feature_class, raster):
    """Compare the feature resolution to the raster resolution.
    Returns a value from 0-100 describing the percent of features that are
    larger than the area of one cell in the raster"""
    fc_count = int(arcpy.GetCount_management(feature_class).getOutput(0))

    # ask what the area of a cell in the raster is
    desc = arcpy.Describe(raster)
    cell_size = desc.meanCellHeight
    cell_area = desc.meanCellHeight * desc.meanCellWidth

    # ask what proportion of features are smaller than that
    small_count = 0
    with arcpy.da.SearchCursor(feature_class, ["SHAPE@AREA"]) as cursor:
        for row in cursor:
            if row[0] < cell_area:
                small_count += 1

    percent_ok = 100*(1 - (small_count/float(fc_count)))

    return((percent_ok))


def shortname(path):
    return os.path.splitext(os.path.basename(path))[0]


def create_temp_GDB(name):
    temp_dir = os.path.join(tempfile.gettempdir(), name)
    index = 0
    while os.path.exists(temp_dir):
        temp_dir = os.path.join(tempfile.gettempdir(), '{0}{1}'.format(name, index))
        index += 1
    os.mkdir(temp_dir)
    arcpy.CreateFileGDB_management(temp_dir, '{0}.gdb'.format(name))
    return(os.path.join(temp_dir,'{0}.gdb'.format(name)))


def lengthen_field(table_or_fc, field, new_length):
    old_field = arcpy.ListFields(table_or_fc, field)
    temp_field = 't_' + field
    arcpy.AddField_management(table_or_fc, temp_field, old_field[0].type, field_length = new_length)
    arcpy.CalculateField_management(table_or_fc, temp_field, '!{}!'.format(field), 'PYTHON')
    arcpy.DeleteField_management(table_or_fc, field)
    arcpy.AddField_management(table_or_fc, field, old_field[0].type, field_length = new_length)
    arcpy.CalculateField_management(table_or_fc, field, '!{}!'.format(temp_field), 'PYTHON')
    arcpy.DeleteField_management(table_or_fc, temp_field)