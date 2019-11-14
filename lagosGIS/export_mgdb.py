import os
import arcpy
import lagosGIS

arcpy.env.workspace = 'in_memory'
OUT_FOLDER = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2019-11-11_Export-LOCUS'
OUT_GDB = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2019-10-18_Export-LOCUS\2019-10-18_LOCUS_Shape.gdb'

# #---------- LOCUS tables--------------

# # Lake information
# lake_info_fields = ['lagoslakeid',
# 'lake_nhdid',
# 'lake_nhdfcode',
# 'lake_nhdftype',
# 'lake_reachcode',
# 'lake_namegnis',
# 'lake_namelagos',
# 'lake_onlandborder',
# 'lake_ismultipart',
# 'lake_missingws',
# # 'lake_shapeflag',
# 'lake_lat_decdeg',
# 'lake_lon_decdeg',
# 'lake_centroidstate',
# 'lake_states',
# 'lake_huc12',
# 'buff100_zoneid',
# 'buff500_zoneid',
# 'ws_zoneid',
# 'nws_zoneid',
# 'hu12_zoneid',
# 'hu8_zoneid',
# 'hu4_zoneid',
# 'county_zoneid',
# 'state_zoneid',
# 'epanutr4_zoneid',
# 'wwf_zoneid',
# 'mlra_zoneid',
# 'bailey_zoneid',
# 'neon_zoneid'
#           ]
#
# lake_fc = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
# print('lake info')
# fc_fields = [f.name for f in arcpy.ListFields(lake_fc)]
# for f in lake_info_fields:
#     if f not in fc_fields:
#         print f
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
#
# Lake characteristics
lake_char_fields = [
'lagoslakeid',
'lake_elevation_m',
'lake_waterarea_ha',
'lake_totalarea_ha',
'lake_islandarea_ha',
'lake_perimeter_m',
'lake_islandperimeter_m',
 'lake_shorelinedevfactor_nounits',
# 'lake_mbgconhull_length_m',
# 'lake_mbgconhull_width_m',
# 'lake_mbgconhull_orientation_deg',
# 'lake_mbgrect_length_m',
# 'lake_mbgrect_width_m',
# 'lake_mbgrect_arearatio',
# 'lake_meanwidth_m',
'lake_connectivity_class',
'lake_connectivity_fluctuates',
'lake_connectivity_permanent',
# 'lake_lakes4ha_upstream_ha',
# 'lake_lakes4ha_upstream_n',
# 'lake_lakes1ha_upstream_ha',
# 'lake_lakes1ha_upstream_n',
# 'lake_lakes10ha_upstream_n',
# 'lake_lakes10ha_upstream_ha'
'lake_glaciatedlatewisc',
]

lake_fc = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'

print('lake char')
lake_fields = [f.name for f in arcpy.ListFields(lake_fc)]
for f in lake_char_fields:
    if f not in lake_fields:
        print f
temp_lake_char = lagosGIS.select_fields(lake_fc, 'temp_lake_char', lake_char_fields, convert_to_table=True)
lake_char = lagosGIS.export_to_csv('temp_lake_char', OUT_FOLDER, new_table_name = 'lake_characteristics',
                                   rename_fields=False, export_qa_version=False)

# # WS watersheds
# ws_fields = [
# 'lagoslakeid',
# 'ws_zoneid',
# 'ws_subtype',
# 'ws_equalsnws',
# 'ws_onlandborder',
# 'ws_oncoast',
# 'ws_inusa_pct',
# 'ws_includeshu4inlet',
# 'ws_ismultipart',
# 'ws_sliverflag',
# 'ws_states',
# 'ws_focallakewaterarea_ha',
# 'ws_area_ha',
# 'ws_perimeter_m',
# 'ws_lake_arearatio',
# 'ws_mbgconhull_length_m',
# 'ws_mbgconhull_width_m',
# 'ws_mbgconhull_orientation_deg',
# 'ws_meanwidth_m'
#     ]
#
# # NWS watersheds
# nws_fields = [
# 'lagoslakeid',
# 'nws_zoneid',
# 'nws_onlandborder',
# 'nws_oncoast',
# 'nws_inusa_pct',
# 'nws_includeshu4inlet',
# 'nws_ismultipart',
# 'nws_states',
# 'nws_focallakewaterarea_ha',
# 'nws_area_ha',
# 'nws_perimeter_m',
# 'nws_mbgconhull_length_m',
# 'nws_mbgconhull_width_m',
# 'nws_mbgconhull_orientation_deg',
# 'nws_meanwidth_m'
#     ]
#
# ws = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Spatial_Classifications\ws'
# nws = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Spatial_Classifications\nws'
#
# print('ws')
# ws_fc_fields = [f.name for f in arcpy.ListFields(ws)]
# for f in ws_fields:
#     if f not in ws_fc_fields:
#         print f
# temp_lake_ws = lagosGIS.select_fields(ws, 'temp_lake_ws', ws_fields, convert_to_table=True)
# lake_sheds_ws = lagosGIS.export_to_csv('temp_lake_ws', OUT_FOLDER, new_table_name='lake_watersheds_ws',
#                                    rename_fields=False, export_qa_version=False)
#
# print('nws')
# nws_fc_fields = [f.name for f in arcpy.ListFields(nws)]
# for f in nws_fields:
#     if f not in nws_fc_fields:
#         print f
# temp_lake_nws = lagosGIS.select_fields(nws, 'temp_lake_nws', nws_fields, convert_to_table=True)
# lake_sheds_ws = lagosGIS.export_to_csv('temp_lake_nws', OUT_FOLDER, new_table_name='lake_watersheds_nws',
#                                    rename_fields=False, export_qa_version=False)

# print('ws shape')
# ws_shp_export = os.path.join(OUT_GDB, 'ws')
# ws_shape = lagosGIS.select_fields(ws, ws_shp_export, ['lagoslakeid', 'ws_zoneid'])
#
# print('nws shape')
# nws_shp_export = os.path.join(OUT_GDB, 'nws')
# nws_shape = lagosGIS.select_fields(nws, nws_shp_export, ['lagoslakeid', 'nws_zoneid'])