# filename: merge_subregion_outputs.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (not in ArcGIS Toolbox)
# purpose: These functions assist with merging and deduplicating GIS outputs for analyses that had to be run at the
# subregion level.

import os
import arcpy
from arcpy import management as DM
import lagosGIS

# Setup
NUM_SUBREGIONS = 202

def merge_matching_master(output_list, output_fc, master_file, join_field = 'lagoslakeid'):
    """Merges subregion-level GIS files and filters them to match a master merged file based on selected identifier"""
    arcpy.env.scratchWorkspace = os.getenv("TEMP")
    arcpy.env.workspace = arcpy.env.scratchGDB
    if arcpy.Exists('outputs_merged'):
        arcpy.Delete_management('outputs_merged')

    if len(output_list) == NUM_SUBREGIONS:
        arcpy.AddMessage("Merging outputs...")
        outputs_merged = lagosGIS.efficient_merge(output_list, 'outputs_merged')
        arcpy.AddMessage("Merge completed, trimming to master list...")
        data_type = arcpy.Describe(outputs_merged).dataType

        master_set = {r[0] for r in arcpy.da.SearchCursor(master_file, join_field)}
        with arcpy.da.UpdateCursor(outputs_merged, join_field) as u_cursor:
            for row in u_cursor:
                if row[0] not in master_set:
                    u_cursor.deleteRow()
        if data_type == "FeatureClass":
            DM.CopyFeatures(outputs_merged, output_fc)
        else:
            DM.CopyRows(outputs_merged, output_fc)

    else:
        print("Incomplete list of inputs. There should be {} inputs.".format(NUM_SUBREGIONS))

    return output_fc


def store_rules(field_list, priorities_list, rules_list, sort_list=[]):
    """
    Creates a ruleset to manage deduplication of features merged from multiple subregions.
    :param field_list: List of fields needed to make rules
    :param priorities_list: List of integers, lowest (1) indicates highest priority rule
    :param rules_list: List of values 'max', 'min', or 'custom_sort', indicates rule type to use
    :param sort_list: If rule type is 'custom_sort', list of values in the desired sorting order
    :return:
    """

    VALID_RULES = {'max', 'min', 'custom_sort'}
    if not sort_list:
        sort_list = [None] * len(field_list)
    for rule in rules_list:
        if rule not in VALID_RULES:
            raise ValueError("store_rules: rule must be one of %r" % VALID_RULES)

    rules_df = []
    rule_keys = ['field', 'priority', 'rule', 'sort']
    for f, p, r, s in zip(field_list, priorities_list, rules_list, sort_list):
        rule = dict(zip(rule_keys, [f, p, r, s]))
        rules_df.append(rule)
    order = [item['priority'] for item in rules_df]
    rules_df = dict(zip(order, rules_df))
    return rules_df

# rule_dictionary is a dictionary of dictionaries with the priority as the key
# like ('1': {'field': 'id', 'priority': 1, 'rule': 'custom_sort})


def deduplicate(merged_file, rule_dictionary, unique_id='lagoslakeid'):
    """
    De-duplicates a file with features merged from subregion-level outputs using a stored ruleset.
    In this context, "duplicates" are duplicates of the intended unique identfier but the features may vary in size,
    shape, etc. and the ruleset will guide whether the largest feature or longest feature is taken, etc.
    :param merged_file: Feature class or file with the merged features containing some duplicates
    :param rule_dictionary: The result of store_rules
    :param unique_id: The identifier that should be unique once features are de-duplicated.
    :return:
    """
    order_fields = []
    sort_fields = []
    for i in range(1, len(rule_dictionary) + 1): # priority order
        rule = rule_dictionary[i]
        if rule['rule'] == 'min':
            order_fields.append('{} asc'.format(rule['field']))
        elif rule['rule'] == 'max':
            order_fields.append('{} desc'.format(rule['field']))
        else:
            sort_field = '{}_SORT'.format(rule['field'])
            sort_fields.append(sort_field)
            if not arcpy.ListFields(merged_file, sort_field):
                DM.AddField(merged_file, sort_field, 'SHORT')
            # Calculate new sort field with numeric order based on custom sort order
            with arcpy.da.UpdateCursor(merged_file, [rule['field'], sort_field]) as cursor:
                for row in cursor:
                    row[1] = rule['sort'].index(row[0])
                    cursor.updateRow(row)

            order_fields.append('{} asc'.format(sort_field))
    order_by_clause = 'ORDER BY {}'.format(', '.join(order_fields))
    print(order_by_clause)

    print("Finding duplicate ids...")
    freq = arcpy.Frequency_analysis(merged_file, 'in_memory/freq', unique_id)
    dupe_ids = [row[0] for row in arcpy.da.SearchCursor(freq, unique_id, '''"FREQUENCY" > 1''')]

    for id in dupe_ids:
        if arcpy.ListFields(merged_file, '{}*'.format(unique_id))[0].type == 'String':
            filter = '''{} = '{}' '''.format(unique_id, id)
        else:
            filter = '''{} = {} '''.format(unique_id, id)
        with arcpy.da.UpdateCursor(merged_file, '*', filter, sql_clause =
        (None, order_by_clause)) as dupes_cursor:
            counter = 0
            # Deletes all but the first sorted row.
            for dupe_row in dupes_cursor:
                print(dupe_row)
                # time.sleep(.1)
                if counter != 0:
                    print("DUPLICATE")
                    dupes_cursor.deleteRow()
                counter += 1
        print(' ')

    arcpy.Delete_management('in_memory/freq')
    for f in sort_fields:
        DM.DeleteField(merged_file, f)

