# filename: export_gis_and_info_tables.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS, GEO
# tool type: code journal, internal use only
# purpose: Includes the specifications to export GIS layers and information tables from the internal spatial extents
# file geodatabase. This was for LAGOS-US internal use.

import os
import arcpy
import lagosGIS

arcpy.env.workspace = 'in_memory'
arcpy.env.overwriteOutput = True
CURRENT_WORKING_GDB = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.9.gdb'
OUT_FOLDER_LOCUS = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2021-05-20_Export-LOCUS'
OUT_GDB_LOCUS = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2021-05-20_Export-LOCUS\gis_locus_v1.0.gdb'
OUT_FOLDER_GEO = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2021-11-28_Export-GEOGIS'
OUT_GDB_GEO = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2021-11-28_Export-GEOGIS\gis_geo_v1.0.gdb'
OUT_GDB_SIMPLE = r'D:\Continental_Limnology\Data_Working\Tool_Execution\2021-11-28_Export-GEOGIS\simple_gis_geo_v1.0.gdb'
FIELD_WARN_MSG = "WARNING: Specified fields missing from input dataset ({})"

# ---SET UP EXPORT NAMES/REQUIREMENTS-----------------------------------------------------------------------------
lake_fc = os.path.join(CURRENT_WORKING_GDB, 'LAGOS_US_All_Lakes_1ha')
lake_fc_fields = [f.name for f in arcpy.ListFields(lake_fc)]

# lake information
lake_info_fields = ['lagoslakeid',
                    'lake_nhdid',
                    'lake_nhdfcode',
                    'lake_nhdftype',
                    'lake_reachcode',
                    'lake_namegnis',
                    'lake_namelagos',
                    'lake_onlandborder',
                    'lake_ismultipart',
                    'lake_missingws',
                    'lake_shapeflag',
                    'lake_lat_decdeg',
                    'lake_lon_decdeg',
                    'lake_elevation_m',
                    'lake_centroidstate',
                    'lake_states',
                    'lake_county',
                    'lake_countyfips',
                    'lake_huc12',
                    'buff100_zoneid',
                    'buff500_zoneid',
                    'ws_zoneid',
                    'nws_zoneid',
                    'hu12_zoneid',
                    'hu8_zoneid',
                    'hu4_zoneid',
                    'county_zoneid',
                    'state_zoneid',
                    'epanutr_zoneid',
                    'omernik3_zoneid',
                    'wwf_zoneid',
                    'mlra_zoneid',
                    'bailey_zoneid',
                    'neon_zoneid'
                    ]
lake_shp_export = os.path.join(OUT_GDB_LOCUS, 'lake')
lake_shp_pt_export = os.path.join(OUT_GDB_LOCUS, 'lake_as_point')

# lake characteristics
lake_char_fields = [
    'lagoslakeid',
    'lake_waterarea_ha',
    'lake_totalarea_ha',
    'lake_islandarea_ha',
    'lake_perimeter_m',
    'lake_islandperimeter_m',
    'lake_shorelinedevfactor',
    'lake_mbgconhull_length_m',
    'lake_mbgconhull_width_m',
    'lake_mbgconhull_orientation_deg',
    'lake_mbgrect_length_m',
    'lake_mbgrect_width_m',
    'lake_mbgrect_arearatio',
    'lake_meanwidth_m',
    'lake_connectivity_class',
    'lake_connectivity_fluctuates',
    'lake_connectivity_permanent',
    'lake_lakes4ha_upstream_ha',
    'lake_lakes4ha_upstream_n',
    'lake_lakes1ha_upstream_ha',
    'lake_lakes1ha_upstream_n',
    'lake_lakes10ha_upstream_n',
    'lake_lakes10ha_upstream_ha',
    'lake_glaciatedlatewisc',
]

# watersheds
ws = os.path.join(CURRENT_WORKING_GDB, 'ws')
nws = os.path.join(CURRENT_WORKING_GDB, 'nws')
ws_fc_fields = [f.name for f in arcpy.ListFields(ws)]
nws_fc_fields = [f.name for f in arcpy.ListFields(nws)]
ws_shp_export = os.path.join(OUT_GDB_LOCUS, 'ws')
nws_shp_export = os.path.join(OUT_GDB_LOCUS, 'nws')

ws_fields = [
    'lagoslakeid',
    'ws_zoneid',
    'ws_subtype',
    'ws_equalsnws',
    'ws_onlandborder',
    'ws_oncoast',
    'ws_inusa_pct',
    'ws_includeshu4inlet',
    'ws_ismultipart',
    'ws_lat_decdeg',
    'ws_lon_decdeg',
    'ws_sliverflag',
    'ws_states',
    'ws_focallakewaterarea_ha',
    'ws_area_ha',
    'ws_perimeter_m',
    'ws_lake_arearatio',
    'ws_mbgconhull_length_m',
    'ws_mbgconhull_width_m',
    'ws_mbgconhull_orientation_deg',
    'ws_meanwidth_m'
]

nws_fields = [
    'lagoslakeid',
    'nws_zoneid',
    'nws_onlandborder',
    'nws_oncoast',
    'nws_inusa_pct',
    'nws_includeshu4inlet',
    'nws_ismultipart',
    'nws_lat_decdeg',
    'nws_lon_decdeg',
    'nws_states',
    'nws_focallakewaterarea_ha',
    'nws_area_ha',
    'nws_perimeter_m',
    'nws_lake_arearatio',
    'nws_mbgconhull_length_m',
    'nws_mbgconhull_width_m',
    'nws_mbgconhull_orientation_deg',
    'nws_meanwidth_m'
]

# catchments
cat = os.path.join(CURRENT_WORKING_GDB, 'catchment')
cat_shp_export = os.path.join(OUT_GDB_LOCUS, 'catchment')
cat_fields = ['lagoslakeid',
              'Permanent_Identifier',
              'NHDPlusID',
              'SourceFC',
              'Permanent_Identifier',
              'VPUID']

# great lakes


# geo spatial divisions
zones = ['buff100',
         'buff500',
         'nws',
         'ws',
         'hu12',
         'hu8',
         'hu4',
         'county',
         'state',
         'wwf',
         'mlra',
         'bailey',
         'neon',
         'omernik3',
         'epanutr']


# ---EXPORT LOCUS TABLES & GIS-------------------------------------------------------------------------------------
def export_locus(export_info=True, export_gis=True):
    """
    Export the tables that comprise LAGOS-US LOCUS module.
    :param export_info: Boolean. Whether to export *_information.csv tables
    :param export_gis: Boolean. Whether to export GIS datasets
    :return: None
    """
    if export_info:
        # lake_information
        print('lake_information')
        for f in lake_info_fields:
            if f not in lake_fc_fields:
                print(FIELD_WARN_MSG.format(f))
        temp_lake_info = lagosGIS.select_fields(lake_fc, 'temp_lake_info', lake_info_fields, convert_to_table=True)
        lagosGIS.export_to_csv(temp_lake_info, OUT_FOLDER_LOCUS, new_table_name='lake_information',
                               rename_fields=False, export_qa_version=False)

        # lake_characteristics
        print('lake_characteristics')
        for f in lake_char_fields:
            if f not in lake_fc_fields:
                print(FIELD_WARN_MSG.format(f))
        temp_lake_char = lagosGIS.select_fields(lake_fc, 'temp_lake_char', lake_char_fields, convert_to_table=True)
        lagosGIS.export_to_csv(temp_lake_char, OUT_FOLDER_LOCUS, new_table_name = 'lake_characteristics',
                               rename_fields=False, export_qa_version=False)

        # lake_watersheds
        print('watersheds')
        for f in ws_fields:
            if f not in ws_fc_fields:
                print(FIELD_WARN_MSG.format(f))
        temp_lake_ws = lagosGIS.select_fields(ws, 'temp_lake_ws', ws_fields, convert_to_table=True)
        lagosGIS.export_to_csv(temp_lake_ws, OUT_FOLDER_LOCUS, new_table_name='lake_watersheds_ws',
                               rename_fields=False, export_qa_version=False)

        for f in nws_fields:
            if f not in nws_fc_fields:
                print(FIELD_WARN_MSG.format(f))
        temp_lake_nws = lagosGIS.select_fields(nws, 'temp_lake_nws', nws_fields, convert_to_table=True)
        lagosGIS.export_to_csv(temp_lake_nws, OUT_FOLDER_LOCUS, new_table_name='lake_watersheds_nws',
                               rename_fields=False, export_qa_version=False)

    if export_gis:
        print('lake shape layers')
        lagosGIS.select_fields(lake_fc, lake_shp_export, ['lagoslakeid'])
        lagosGIS.select_fields(lake_fc + '_points', lake_shp_pt_export, ['lagoslakeid', 'nws_zoneid', 'ws_zoneid'])

        print('watersheds shape layers')
        lagosGIS.select_fields(ws, ws_shp_export, ['lagoslakeid', 'ws_zoneid'])
        lagosGIS.select_fields(nws, nws_shp_export, ['lagoslakeid', 'nws_zoneid'])

        # catchment layer
        print('catchments shape layers')
        lagosGIS.select_fields(cat, cat_shp_export, cat_fields)


# ---EXPORT GEO INFORMATION & GIS-------------------------------------------------------------------------------------
def export_zone(zone_name, export_info=True, export_gis=True, export_simple_gis=True, export_glaciation=True):
    """
    Exports a single spatial division's information table and GIS dataset for LAGOS-US GEO spatial divisions. Does not
    export the rest of the GEO module!
    :param zone_name: Shortname/prefix for the spatial division to be exported
    :param export_info: Boolean. Whether to export *_information.csv table
    :param export_gis: Boolean. Whether to export GIS database
    :param export_simple_gis: Boolean. Whether to export simple GIS database
    :param export_glaciation: Boolean. Whether to export glaciation metric to table named "*_glaciatedlatewisc"
    :return: None
    """

    zone_fc = os.path.join(CURRENT_WORKING_GDB, zone_name)

    if export_info:
        # Specify the right fields for this spatial division
        field_vars = ['zoneid',
                      'sourceid',
                      'name',
                      'fips',
                      'states',
                      'area_ha',
                      'perimeter_m',
                      'originalarea_pct',
                      'lat_decdeg',
                      'lon_decdeg',
                      'inusa_pct',
                      'onlandborder',
                      'oncoast',
                      'ismultipart']
        if not arcpy.ListFields(zone_fc, field_vars[3]):
            field_vars.pop(3)
        lake_zones = ['buff100', 'buff500', 'nws', 'ws']
        if zone_name in lake_zones:
            field_vars.remove('sourceid')
            field_vars.remove('name')
            field_vars.remove('originalarea_pct')
        if zone_name == 'state':
            field_vars.remove('states')
        field_list = ['{}_{}'.format(zone_name, f) for f in field_vars]
        if 'sourceid' in field_list[1]:
            field_list[1] = arcpy.ListFields(zone_fc, '*sourceid*')[0].name

        # Check for missing fields
        for f in field_list:
            if not arcpy.ListFields(zone_fc, f):
                print(FIELD_WARN_MSG.format(f))

        # zone_information
        print('zone_information (subset for division {})'.format(zone_name))
        temp_zone_fc = lagosGIS.select_fields(zone_fc, 'temp_zone_fc', field_list, convert_to_table=True)
        lagosGIS.export_to_csv(temp_zone_fc, OUT_FOLDER_GEO,
                               new_table_name='{}_information'.format(zone_name),
                               rename_fields=False, export_qa_version=False)

    if export_gis:
        # zone shape layers
        if zone_name not in ('ws', 'nws'):  # which were published in LOCUS already
            print('{} shape layer'.format(zone_name))
            zone_shp_export = os.path.join(OUT_GDB_GEO, zone_name)
            lagosGIS.select_fields(zone_fc, zone_shp_export, ['{}_zoneid'.format(zone_name)])

    if export_simple_gis:
        # simple shape layers
        # created with
        # SimplifyPolygon(zone_fc, out_fc, "BEND_SIMPLIFY, "2500 Meters", error_option="RESOLVE_ERRORS")
        print('{} simple shape layer'.format(zone_name))
        zone_fc = os.path.join(CURRENT_WORKING_GDB, 'simple_' + zone_name)
        simple_shp_export = os.path.join(OUT_GDB_SIMPLE, 'simple_' + zone_name)
        lagosGIS.select_fields(zone_fc, simple_shp_export, ['{}_zoneid'.format(zone_name)])

        # HU12 gets two options because it's on the edge of usability
        if zone_name == 'hu12':
            zone_poly_fc = zone_fc + '_poly'
            simple_poly_export = simple_shp_export + '_poly'
            lagosGIS.select_fields(zone_poly_fc, simple_poly_export, ['{}_zoneid'.format(zone_name)])

    if export_glaciation:
        field_list = ['{}_{}'.format(zone_name, f) for f in ['zoneid', 'glaciatedlatewisc_pct']]
        for f in field_list:
            if not arcpy.ListFields(zone_fc, f):
                print(FIELD_WARN_MSG.format(f))
        temp_zone_fc = lagosGIS.select_fields(zone_fc, 'temp_zone_fc', field_list, convert_to_table=True)
        lagosGIS.export_to_csv(temp_zone_fc, OUT_FOLDER_GEO,
                               new_table_name='{}_glaciatedlatewisc'.format(zone_name),
                               rename_fields=False, export_qa_version=False)


# ---RUN ALL-----------------------------------------------------------------------------------------------------
# export_locus()
for z in zones:
    export_zone(z, False, True, False, False)

# # add lake to simple gis
# simple_lake = os.path.join(OUT_GDB_SIMPLE, 'simple_lake')
# lagosGIS.select_fields(lake_fc + '_points', simple_lake, ['lagoslakeid'])
