# filename: dams_link_lake_junctions_doit.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): CONN
# tool type: code journal, internal use, batch run

import os
import arcpy

DAMS =r'D:\Continental_Limnology\Data_Downloaded\NABDv2_Dams_DanaInfante_Unpublished\Unzipped Original\NABD_V2_beta.shp'
INLETS = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2020-07-23_Inlets_Outlets\2020-07-23_Inlets_Outlets.gdb\LAGOS_inlets'
OUTLETS = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2020-07-23_Inlets_Outlets\2020-07-23_Inlets_Outlets.gdb\LAGOS_outlets'
inlets_name = os.path.basename(INLETS)
outlets_name = os.path.basename(OUTLETS)

arcpy.env.workspace = 'in_memory'
near = arcpy.GenerateNearTable_analysis(DAMS, [INLETS, OUTLETS], 'near',
                                 search_radius='250 Kilometers', closest='ALL', closest_count='3')

# convert FIDs to IDs
fid_dams = {r[0]:r[1] for r in arcpy.da.SearchCursor(DAMS, ['FID', 'DAMID'])}
fid_inlets = {r[0]:r[1] for r in arcpy.da.SearchCursor(INLETS, ['OBJECTID', 'lagoslakeid'])}
fid_outlets = {r[0]:r[1] for r in arcpy.da.SearchCursor(OUTLETS, ['OBJECTID', 'lagoslakeid'])}

arcpy.AddField_management(near, 'DAMID', 'LONG')
arcpy.AddField_management(near, 'near_lagoslakeid', 'LONG')

with arcpy.da.UpdateCursor(near, ['IN_FID',
                                    'NEAR_FID',
                                    'NEAR_FC',
                                    'DAMID',
                                    'near_lagoslakeid'
                                  ]) as cursor:
    for row in cursor:
        in_fid, near_fid, near_fc, damid, n_lagoslakeid = row
        damid = fid_dams[in_fid]
        if near_fc == INLETS:
            n_lagoslakeid = fid_inlets[near_fid]
        else:
            n_lagoslakeid = fid_outlets[near_fid]
        near_fc = os.path.basename(near_fc)
        row = in_fid, near_fid, near_fc, damid, n_lagoslakeid
        cursor.updateRow(row)

# pivot closest junctions 1 through 3
pivot_dist = arcpy.PivotTable_management(near, ['DAMID'], 'NEAR_RANK', 'NEAR_DIST', 'pivot_dist')
for f in arcpy.ListFields(pivot_dist, 'NEAR_RANK*'):
    arcpy.AlterField_management(pivot_dist, f.name, f.name + '_DIST', clear_field_alias=True)
pivot_fc = arcpy.PivotTable_management(near, ['DAMID'], 'NEAR_RANK', 'NEAR_FC', 'pivot_fc')
for f in arcpy.ListFields(pivot_fc, 'NEAR_RANK*'):
    arcpy.AlterField_management(pivot_fc, f.name, f.name + '_FC', clear_field_alias=True)
pivot_id = arcpy.PivotTable_management(near, ['DAMID'], 'NEAR_RANK', 'near_lagoslakeid', 'pivot_id')
for f in arcpy.ListFields(pivot_id, 'NEAR_RANK*'):
    arcpy.AlterField_management(pivot_id, f.name, f.name + '_lagoslakeid', clear_field_alias=True)

arcpy.JoinField_management(pivot_id, 'DAMID', pivot_dist, 'DAMID')
arcpy.JoinField_management(pivot_id, 'DAMID', pivot_fc, 'DAMID')
for field_name in ['DAMID_1', 'near_lagoslakeid', 'DAMID_12', 'near_lagoslakeid_1']:
    arcpy.DeleteField_management(pivot_id, field_name)


arcpy.AddField_management(pivot_id, 'lagoslakeid', 'LONG')
arcpy.AddField_management(pivot_id, 'ambiguous_dir', 'TEXT', field_length=1)
arcpy.AddField_management(pivot_id, 'ambiguous_lake', 'TEXT', field_length=1)
arcpy.AddField_management(pivot_id, 'dam_link', 'TEXT', field_length=50)

with arcpy.da.UpdateCursor(pivot_id, '*') as cursor:
    for row in cursor:
        damid, lagos1, lagos2, lagos3, dist1, dist2, dist3, fc1, fc2, fc3, lagoslakeid, amb_dir, amb_lake, dam_link = row[1:]

        amb_dir = 'Y' if ((dist2-dist1 < 100 and dist1 > 25) or dist2-dist1 < 50) and fc1 <> fc2 else 'N'
        amb_lake = 'Y' if ((dist2-dist1 < 100 and dist1 > 25) or dist2-dist1 < 50) and lagos1 <> lagos2 else 'N'

        if dist1 < 250 and amb_dir == 'N' and amb_lake == 'N':
            if fc1 == inlets_name:
                dam_link = 'lake downstream of dam'
                lagoslakeid = lagos1
            else:
                dam_link = 'lake upstream of dam'
            lagoslakeid = lagos1
        if dist1 > 500:
            dam_link = 'dam over 500m from any lake junction'
        row[1:] = damid, lagos1, lagos2, lagos3, dist1, dist2, dist3, fc1, fc2, fc3, lagoslakeid, amb_dir, amb_lake, dam_link
        cursor.updateRow(row)


arcpy.CopyRows_management(pivot_id, r'C:\Users\smithn78\Documents\ArcGIS\Default.gdb\Dams_In_Out')
