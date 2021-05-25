from datetime import datetime as dt
import os
import arcpy
import lagosGIS
import watershed_delineation.postprocess_watersheds as postprocess
from watershed_delineation.watersheds_toolchain_v2 import make_run_list
from watershed_delineation.watersheds_toolchain_v2 import HU4
import merge_subregion_outputs

LAGOS_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.8.gdb\Lakes\LAGOS_US_All_Lakes_1ha'

CATCHMENTS_PATH = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds_v2_correct\watersheds_{hu4}.gdb\lagos_catchments_{hu4}'
LAKE_SHEDS_PATH = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds_v2_correct\watersheds_{hu4}.gdb\lagos_watersheds_{hu4}_interlake'
NETWORK_SHEDS_PATH = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds_v2_correct\watersheds_{hu4}.gdb\lagos_watersheds_{hu4}_network'
PARENT_DIRECTORY = 'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds_v2_correct'
NHD_GDB = r"F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution_COMPLETE\Unzipped_Original\Vectors\NHDPLUS_H_{hu4}_HU4_GDB.gdb"

output_gdb = os.path.join(PARENT_DIRECTORY, 'merged_watersheds.gdb')
output_ws = os.path.join(output_gdb, 'ws')
temp_nws = os.path.join(output_gdb, 'temp_nws')
output_nws = os.path.join(output_gdb, 'nws')
output_cat = os.path.join(output_gdb, 'catchment')

def merge_watersheds(parent_directory, output_fc, tag):
    merge_fcs = []
    walk = arcpy.da.Walk(parent_directory, datatype='FeatureClass')
    for dirpath, dirnames, filenames in walk:
        for filename in filenames:
            if tag in filename and 'old' not in filename and 'prepatch' not in filename and 'undissolved' not in filename:
                merge_fcs.append(os.path.join(dirpath, filename))

    # merge the main results
    if tag == 'interlake':
        output_fc = lagosGIS.efficient_merge(merge_fcs, output_fc)

    elif tag == 'network':
        # output_fc = lagosGIS.efficient_merge(merge_fcs, output_fc, "equalsiws = 'N'")
        output_fc = lagosGIS.efficient_merge(merge_fcs, output_fc)


    elif tag == 'catchment':
        for fc in merge_fcs:
            print fc
        output_fc = lagosGIS.efficient_merge(merge_fcs, output_fc, 'lagoslakeid IS NOT NULL')

    return output_fc

# make the run list
run_list = make_run_list(HU4)
great_lakes =['0418', '0420', '0427', '0429', '0430']
run_list.extend(great_lakes)
run_list.remove('0415')

# add VPUIDs to ws, nws
for hu4 in run_list:
    nws = NETWORK_SHEDS_PATH.format(hu4=hu4)
    ws = LAKE_SHEDS_PATH.format(hu4=hu4)
    if not arcpy.ListFields(nws, 'VPUID'):
        print(hu4)
        arcpy.AddField_management(nws, 'VPUID', 'TEXT', field_length=4)
        arcpy.CalculateField_management(nws, 'VPUID', "'{}'".format(hu4), 'PYTHON')
    if not arcpy.ListFields(ws, 'VPUID'):
        print(hu4)
        arcpy.AddField_management(ws, 'VPUID', 'TEXT', field_length=4)
        arcpy.CalculateField_management(ws, 'VPUID', "'{}'".format(hu4), 'PYTHON')

add lagoslakeid to catchments
permid_lagosid = {r[0]: r[1] for r in arcpy.da.SearchCursor(LAGOS_LAKES, ['Permanent_Identifier', 'lagoslakeid'])}
for hu4 in run_list:
    print(hu4)
    catchments = CATCHMENTS_PATH.format(hu4=hu4)
    arcpy.AddField_management(catchments, 'lagoslakeid', 'LONG')
    with arcpy.da.UpdateCursor(catchments, ['Permanent_Identifier', 'lagoslakeid']) as u_cursor:
        for row in u_cursor:
            row[1] = permid_lagosid.get(row[0])
            u_cursor.updateRow(row)

post-process ws individually
for hu4 in run_list:
    ws = LAKE_SHEDS_PATH.format(hu4=hu4)
    nws = NETWORK_SHEDS_PATH.format(hu4=hu4)
    if arcpy.Exists(ws):
        print("{} at {}".format(hu4, dt.now()))
        nhd_gdb = NHD_GDB.format(hu4=hu4)
        postprocess.process_ws(ws, 'ws', nws, nhd_gdb, fits_naming_standard=False)


for hu4 in run_list:
    nws = NETWORK_SHEDS_PATH.format(hu4=hu4)
    if not arcpy.ListFields(nws, 'VPUID'):
        print(hu4)
        arcpy.AddField_management(nws, 'VPUID', 'TEXT', field_length=4)
        arcpy.CalculateField_management(nws, 'VPUID', "'{}'".format(hu4), 'PYTHON')

# Mergers and post-processing NWS
print("Merging lake watersheds...")
merge_watersheds(PARENT_DIRECTORY, output_ws, 'interlake')

print("Merging network watersheds...")
merge_watersheds(PARENT_DIRECTORY, temp_nws, 'network')
# Need to dissolve NWS in this run, but re-running network tools has fixed some of them too
dissolve_nws = temp_nws + '_dissolve'
arcpy.Dissolve_management(temp_nws, dissolve_nws, ['Permanent_Identifier', 'VPUID'], "includeshu4inlet MAX")
arcpy.AlterField_management(dissolve_nws, 'MAX_includeshu4inlet', new_field_name = 'includeshu4inlet', clear_field_alias=True)
#
# # filter network watersheds based on equality
postprocess.calc_watershed_equality(output_ws, dissolve_nws)
arcpy.Select_analysis(dissolve_nws, output_nws, "equalsiws = 'N'")
arcpy.Delete_management(temp_nws)
arcpy.Delete_management(dissolve_nws)
postprocess.process_ws(output_nws, 'nws', fits_naming_standard=False)

print("Merging lake catchments only...")
merge_watersheds(PARENT_DIRECTORY, output_cat, 'catchment')

# De-duplicate WS by taking the most connected watershed, which should correspond with the "most-connected" rules used
# for upstream and connectivity, take largest if equally connected
rules_field_list = ['ws_subtype',
                    'ws_area_ha']

priorities = [1,2]
rules = ["custom_sort", "max"]
sort = [['IDWS', 'DWS', 'LC'],
        None]

arcpy.DeleteIdentical_management(output_ws, ['lagoslakeid'] + rules_field_list)
arcpy.AddIndex_management(output_ws, 'lagoslakeid', 'IDX_lagoslakeid')
stored_rules = merge_subregion_outputs.store_rules(rules_field_list, priorities, rules, sort)
merge_subregion_outputs.deduplicate(output_ws, stored_rules)

# De-duplicate NWS by taking watershed from the same VPUID as WS (so the connectivity matches)
arcpy.AddIndex_management(output_nws, 'lagoslakeid', 'IDX_lagoslakeid')
arcpy.DeleteIdentical_management(output_nws, ['lagoslakeid', 'nws_area_ha'])
ws_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(output_ws, ['lagoslakeid', 'VPUID'])}
with arcpy.da.UpdateCursor(output_nws, ['lagoslakeid', 'VPUID']) as cursor:
    for row in cursor:
        # if the VPUID isn't the same as in the de-duplicated WS layer, delete the row
        if row[1] <> ws_dict[row[0]]:
            print("Deleting VPUID {} for lagoslakeid {}".format(row[1], row[0]))
            cursor.deleteRow()

# Fix error with LC subtype and NWS that emerged in Apr/May 2021 run due to patched catchments
# Full re-run would make this code extraneous but it will have no negative effect to run it
# The LC subtype designation was correct but some odd single pixels affected the NWS, this
# step will correct the equality flag and manually delete those watersheds from the NWS layer
ids = []
with arcpy.da.UpdateCursor(output_ws, ['lagoslakeid', 'ws_subtype', 'ws_equalsnws']) as cursor:
    for row in cursor:
        if row[1] == 'LC' and row[2] == 'N':
            row[2] = 'Y'
            ids.append(row[0])
            cursor.updateRow(row)
with arcpy.da.UpdateCursor(output_nws, ['lagoslakeid']) as cursor2:
    for row2 in cursor2:
        if row2[0] in ids:
            cursor2.deleteRow()

# # NOTES May 20, 2021
# Since I dissolved to fix the network watersheds after they merged, I had to manually
# fix ws_equalsnws and then also use that to redefine the ws_subtype (since it is determined
# by the equality)
# A re-run should fix the same thing the dissolve did and not require the manual fixes