# filename: do_national_outlets_inlets.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): CONN
# tool type: code journal, batch run

import os
import arcpy
import lagosGIS

NHD_DIR = r'D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Unzipped_Original'
MAIN_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
OUTPUT_GDB =r'D:\Continental_Limnology\Data_Working\Tool_Execution\2020-07-23_Inlets_Outlets\2020-07-23_Inlets_Outlets.gdb'

# 1) Run them all
arcpy.env.workspace = NHD_DIR
gdbs = arcpy.ListWorkspaces()
for gdb in gdbs:
    huc4 = gdb[-12:-8]
    inlets_output = os.path.join(OUTPUT_GDB, 'inlets_{}'.format(huc4))
    outlets_output = os.path.join(OUTPUT_GDB, 'outlets_{}'.format(huc4))
    print("Creating inlets for {}".format(huc4))
    lagosGIS.locate_lake_inlets(gdb, inlets_output)
    print("Creating outlets for {}".format(huc4))
    lagosGIS.locate_lake_outlets(gdb, outlets_output)

# 2) Merge and de-duplicate
arcpy.env.workspace = OUTPUT_GDB

outlet_fcs = arcpy.ListFeatureClasses('outlets*')
lagosGIS.efficient_merge(outlet_fcs, 'LAGOS_outlets')
arcpy.DeleteIdentical_management('LAGOS_outlets', ['Shape', 'Permanent_Identifier', 'WBArea_Permanent_Identifier'])

inlet_fcs = arcpy.ListFeatureClasses('inlets*')
lagosGIS.efficient_merge(inlet_fcs, 'LAGOS_inlets')
arcpy.DeleteIdentical_management('LAGOS_inlets', ['Shape', 'Permanent_Identifier', 'WBArea_Permanent_Identifier'])

# add lagoslakeid
id_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(MAIN_LAKES, ['Permanent_Identifier', 'lagoslakeid'])}

arcpy.AddField_management('LAGOS_outlets', 'lagoslakeid', 'LONG')
arcpy.AddField_management('LAGOS_inlets', 'lagoslakeid', 'LONG')

for fc in ['LAGOS_outlets', 'LAGOS_inlets']:
    with arcpy.da.UpdateCursor(fc, ['WBArea_Permanent_Identifier', 'lagoslakeid']) as cursor:
        for row in cursor:
            if row[0] in id_dict:
                row[1] = id_dict[row[0]]
            else:
                continue
            cursor.updateRow(row)