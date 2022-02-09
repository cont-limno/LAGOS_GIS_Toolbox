# filename: connectivity_run.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS
# tool type: code journal, internal use, batch run

import os
import arcpy
import lake_connectivity_classification as conn
from watershed_delineation.watersheds_toolchain import make_run_list
import merge_subregion_outputs

HU4 = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.8.gdb\Spatial_Classifications\hu4'
PLUS_DIR = r'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution_COMPLETE\Unzipped_Original\Vectors'
OUTPUT_DIR =  r'D:\Continental_Limnology\Data_Working\Tool_Execution\2021-01-12_ConnRerun_WithClosed\2021-01-12_ConnRerun_WithClosed_NewNHD.gdb'
MASTER_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.8.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
FINAL_OUTPUT =  r'D:\Continental_Limnology\Data_Working\Tool_Execution\2021-01-12_ConnRerun_WithClosed\2021-01-12_ConnRerun_WithClosed_NewNHD.gdb\lake_connectivity'

def conn_run_list():
    run_list = make_run_list(HU4)
    great_lakes =['0418', '0420', '0427', '0429', '0430']
    run_list.extend(great_lakes)
    run_list.remove('0415')
    plus_name = 'NHDPLUS_H_{}_HU4_GDB.gdb'
    paths = [os.path.join(PLUS_DIR, plus_name.format(h)) for h in run_list]

    for p, h in zip(paths, run_list):
        output_path = os.path.join(OUTPUT_DIR, 'conn_{}'.format(h))
        if not arcpy.Exists(output_path):
            print(output_path)
            conn.classify(p, output_path)

conn_run_list()

# #-------MERGE------------------------------------------------
# get files
print("Directory walk...")
walk = arcpy.da.Walk(OUTPUT_DIR, datatype = "Table")
output_list = []
for dirpath, dirnames, filenames in walk:
    for f in filenames:
        if f.startswith("conn"):
            output_list.append(os.path.join(dirpath, f))

rules_field_list = ['lake_connectivity_class',
                   'lake_connectivity_permanent',
                   'lake_connectivity_fluctuates']

priorities = [1, 3, 2]
rules = ["custom_sort", "custom_sort", "min"]
sort = [['DrainageLk', 'Drainage', 'TerminalLk', 'ClosedLk', 'Terminal', 'Closed', 'Headwater', 'Isolated'],
        ['DrainageLk', 'Drainage', 'TerminalLk', 'ClosedLk', 'Terminal', 'Closed', 'Headwater', 'Isolated'],
        None]

# Step 1: Select only necessary fields from output tables pre-merge
# Not necessary for these tables

# Step 2: Merge the tables together
merge_subregion_outputs.merge_matching_master(output_list, FINAL_OUTPUT,
                                              MASTER_LAKES, join_field='Permanent_Identifier')

# Step 3: Add lagoslakeid
master_ids = {r[0]: r[1] for r in arcpy.da.SearchCursor(MASTER_LAKES, ['Permanent_Identifier', 'lagoslakeid'])}

arcpy.AddField_management(FINAL_OUTPUT, 'lagoslakeid', 'LONG')
with arcpy.da.UpdateCursor(FINAL_OUTPUT, ['Permanent_Identifier', 'lagoslakeid']) as cursor:
    for row in cursor:
        row[1] = master_ids[row[0]]
        cursor.updateRow(row)

# Step 4: Delete duplicates using the rule-based de-duplication
arcpy.DeleteIdentical_management(FINAL_OUTPUT, ['lagoslakeid'] + rules_field_list)
arcpy.AddIndex_management(FINAL_OUTPUT, 'lagoslakeid', 'IDX_lagoslakeid')
stored_rules = merge_subregion_outputs.store_rules(rules_field_list, priorities, rules, sort)
merge_subregion_outputs.deduplicate(FINAL_OUTPUT, stored_rules)

# Clean up the table some
arcpy.DeleteField_management(FINAL_OUTPUT, 'nhd_merge_id')
arcpy.DeleteField_management(FINAL_OUTPUT, 'Permanent_Identifier')
