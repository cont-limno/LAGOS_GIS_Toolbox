import os
import arcpy
import lagosGIS

arcpy.env.workspace = 'in_memory'
OUT_FOLDER = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2019-08-26_Export-MGDB'
OUT_GDB = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2019-08-26_Export-MGDB\2019-08-26_Export-MGDB.gdb'
#---------- LOCUS tables--------------

# Lake information
lake_info_fields = ['lagoslakeid',
'lakeid_nhdid',
'lake_nhdfcode',
'lake_nhdftype',
'lake_namegnis',
'lake_namelagos',
'ws_zoneid',
'nws_zoneid',
'hu12_zoneid',
'hu8_zoneid',
'hu4_zoneid',
'county_zoneid',
'state_zoneid',
'epanutr4_zoneid',
'wwf_zoneid',
'mlra_zoneid',
'bailey_zoneid',
'neon_zoneid',
'lake_reachcode',
'lake_onlandborder',
'lake_ismultipart',
'lake_missingws',
'lake_lat_decdeg',
'lake_lon_decdeg',
'lake_state'
          ]

lake_fc = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
# print('lake info')
# temp_lake_info = lagosGIS.select_fields(lake_fc, 'temp_lake_info', lake_info_fields, convert_to_table=True)
# lake_info = lagosGIS.export_to_csv('temp_lake_info', OUT_FOLDER, new_table_name = 'lake_information',
#                                    rename_fields=False, export_qa_version=False)
#
# print('lake shape')
# lake_shp_export = os.path.join(OUT_GDB, 'lake')
# lake_shape = lagosGIS.select_fields(lake_fc, lake_shp_export, ['lagoslakeid'])
#
# print('lake point')
# lake_shp_pt_export = os.path.join(OUT_GDB, 'lake_as_point')
# lake_shape = lagosGIS.select_fields(lake_fc + '_points', lake_shp_pt_export, ['lagoslakeid'])
#
# # Lake characteristics
# lake_char_fields = [
# 'lagoslakeid',
# 'lake_elevation_m',
# 'lake_waterarea_ha',
# 'lake_totalarea_ha',
# 'lake_islandarea_ha',
# 'lake_perimeter_m',
# 'lake_islandperimeter_m',
# # 'lake_shorelinedevfactor',
# # 'lake_mbgconvexhull_length_m',
# # 'lake_mbgconvexhull_width_m',
# # 'lake_mbgconvexhull_orientation_deg',
# # 'lake_mbgrect_length_m',
# # 'lake_mbgrect_width_m',
# # 'lake_mbgrect_area_ha',
# # 'lake_shapeflag',
# # 'lake_meanwidth_m',
# 'lake_connectivity_class',
# 'lake_connectivity_fluctuates',
# 'lake_connectivity_permanent',
# # 'lake_lakes4ha_upstream_ha',
# # 'lake_lakes4ha_upstream_n',
# # 'lake_lakes1ha_upstream_ha',
# # 'lake_lakes1ha_upstream_n',
# # 'lake_lakes10ha_upstream_n',
# # 'lake_lakes10ha_upstream_ha'
# # 'lake_glaciatedlatewisc',
# ]
#
# lake_fc = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
#
# print('lake char')
# lake_fields = [f.name for f in arcpy.ListFields(lake_fc)]
# for f in lake_char_fields:
#     if f not in lake_fields:
#         print f
# temp_lake_char = lagosGIS.select_fields(lake_fc, 'temp_lake_char', lake_char_fields, convert_to_table=True)
# lake_char = lagosGIS.export_to_csv('temp_lake_char', OUT_FOLDER, new_table_name = 'lake_characteristics',
#                                    rename_fields=False, export_qa_version=False)
#
# WS watersheds
ws_fields = [
'ws_zoneid',
'ws_lagoslakeid',
'ws_states',
'ws_focallakewaterarea_ha',
'ws_area_ha',
'ws_perimeter_m',
'ws_mbgconvexhull_length_m',
'ws_mbgconvexhull_width_m',
'ws_mbgconvexhull_orientation_deg',
'ws_meanwidth_m',
'ws_onlandborder',
'ws_oncoast',
'ws_ismultipart',
'ws_inusa_pct',
'ws_equalsnws',
'ws_includeshu4inlet'
    ]

# NWS watersheds
nws_fields = [
'nws_zoneid',
'nws_lagoslakeid',
'nws_states',
'nws_focallakewaterarea_ha',
'nws_area_ha',
'nws_perimeter_m',
'nws_mbgconvexhull_length_m',
'nws_mbgconvexhull_width_m',
'nws_mbgconvexhull_orientation_deg',
'nws_meanwidth_m',
'nws_onlandborder',
'nws_oncoast',
'nws_ismultipart',
'nws_inusa_pct',
'nws_includeshu4inlet'
    ]

ws = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Spatial_Classifications\ws'
nws = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Spatial_Classifications\nws'

# print('ws')
# # ws_fc_fields = [f.name for f in arcpy.ListFields(ws)]
# # for f in ws_fields:
# #     if f not in ws_fc_fields:
# #         print f
# temp_lake_ws = lagosGIS.select_fields(ws, 'temp_lake_ws', ws_fields, convert_to_table=True)
# lake_sheds_ws = lagosGIS.export_to_csv('temp_lake_ws', OUT_FOLDER, new_table_name='lake_watersheds_ws',
#                                    rename_fields=False, export_qa_version=False)

print('nws')
nws_fc_fields = [f.name for f in arcpy.ListFields(nws)]
for f in nws_fields:
    if f not in nws_fc_fields:
        print f
temp_lake_nws = lagosGIS.select_fields(nws, 'temp_lake_nws', nws_fields, convert_to_table=True)
lake_sheds_ws = lagosGIS.export_to_csv('temp_lake_nws', OUT_FOLDER, new_table_name='lake_watersheds_nws',
                                   rename_fields=False, export_qa_version=False)