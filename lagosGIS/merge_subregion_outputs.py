import os
import arcpy
from arcpy import management as DM
import lagosGIS
import time

# Setup
NUM_SUBREGIONS = 202

def merge_matching_master(output_list, output_fc, master_file, join_field = 'lagoslakeid'):
    arcpy.env.scratchWorkspace = os.getenv("TEMP")
    arcpy.env.workspace = arcpy.env.scratchGDB
    if arcpy.Exists('outputs_merged'):
        arcpy.Delete_management('outputs_merged')

    if len(output_list) == NUM_SUBREGIONS:
        field_list = arcpy.ListFields(output_list[0])
        arcpy.AddMessage("Merging outputs...")
        outputs_merged = lagosGIS.efficient_merge(output_list, 'outputs_merged')
        arcpy.AddMessage("Merge completed, trimming to master list...")
        data_type = arcpy.Describe(outputs_merged).dataType
        # if data_type == 'FeatureClass':
        #     outputs_merged_lyr = DM.MakeFeatureLayer(outputs_merged, 'outputs_merged_lyr')
        #     print(int(DM.GetCount(outputs_merged_lyr).getOutput(0)))
        # else:
        #     outputs_merged_lyr = DM.MakeTableView(outputs_merged, 'outputs_merged_lyr')

        master_set = {r[0] for r in arcpy.da.SearchCursor(master_file, join_field)}
        with arcpy.da.UpdateCursor(outputs_merged, join_field) as u_cursor:
            for row in u_cursor:
                if row[0] not in master_set:
                    u_cursor.deleteRow()
        # DM.AddJoin(outputs_merged_lyr, join_field, master_file, join_field, 'KEEP_COMMON')
        #
        # master_prefix = os.path.splitext(os.path.basename(master_file))[0]
        # select_clause = '{}.{} is not null'.format(master_prefix, join_field)
        # DM.SelectLayerByAttribute(outputs_merged_lyr, 'NEW_SELECTION', select_clause)
        # DM.RemoveJoin(outputs_merged_lyr)
        if data_type == "FeatureClass":
            DM.CopyFeatures(outputs_merged, output_fc)
        else:
            DM.CopyRows(outputs_merged, output_fc)
        # copy_field_list = arcpy.ListFields(output_fc)
        # print("Delete fields")
        # print(copy_field_list)
        # drop_fields = [f for f in copy_field_list if f not in field_list]
        # for f in copy_field_list:
        #     if f not in field_list:
        #         print(f)
        #         arcpy.DeleteField_management(output_fc, f)
        #DM.Delete(outputs_merged_lyr)
        #DM.Delete(arcpy.env.scratchGDB)
    else:
        print("Incomplete list of inputs. There should be {} inputs.".format(NUM_SUBREGIONS))
    return output_fc


def store_rules(field_list, priorities_list, rules_list, sort_list = []):
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


def deduplicate(merged_file, rule_dictionary, unique_id = 'lagoslakeid'):
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
                    time.sleep(.1)
                    if counter != 0:
                        print("DUPLICATE")
                        dupes_cursor.deleteRow()
                    counter += 1
            print(' ')

        arcpy.Delete_management('in_memory/freq')
        for f in sort_fields:
            DM.DeleteField(merged_file, f)

