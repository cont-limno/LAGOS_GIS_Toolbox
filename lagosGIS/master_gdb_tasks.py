import os
import arcpy
from arcpy import management as DM
from arcpy import analysis as AN
from datetime import datetime
import lagosGIS

# These tasks are one-off geoprocessing tasks that I wrote code for. This file just saves snippets in case of re-use.
# Things are commented out so I can run later sections, not because they are "defunct."
# It is not a stand-alone script.

# # 2019-05-21
# # update lake field names to naming standard
# with arcpy.da.UpdateCursor('LAGOS_US_All_Lakes_1ha', ['lake_islandarea_ha', 'lake_islandperimeter_m', 'lake_perimeter_m', 'lake_waterarea_ha', 'lake_totalarea_ha', 'Total_Island_Area', 'Perimeter_Without_Islands_km', 'Perimeter_With_Islands_km', 'Area_With_Islands_ha', 'Hectares']) as cursor:
#     for row in cursor:
#         ia, ip, lp, lw, lt, tia, pwoi, pwi, awi, h = row
#         ia = tia
#         ip = (pwi - pwoi) * 1000
#         lp = pwoi * 1000
#         lw = h
#         lt = awi
#         new_row = (ia, ip, lp, lw, lt, tia, pwoi, pwi, awi, h)
#         cursor.updateRow(new_row)
#


# # # 2019-05-28
# mgdb = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb'
# state = os.path.join(mgdb, 'STATE')
# lakes = os.path.join(mgdb, 'LAGOS_US_All_Lakes_1ha_No_Islands')
#
# # 1) add lat/long to all fcs except lakes
def add_lat_long(fc):
    """Add fields for lat and long, per LAGOS naming standard. Only works when fc path is short (use env.workspace.)"""
    lat = '{}_lat_decdeg'.format(fc)
    long = '{}_long_decdeg'.format(fc)
    if not arcpy.ListFields(fc, lat):
        DM.AddField(fc, lat, 'DOUBLE')
    if not arcpy.ListFields(fc, long):
        DM.AddField(fc, long, 'DOUBLE')
    orig_crs = arcpy.SpatialReference(5070)
    new_crs = arcpy.SpatialReference(4326) # NAD83

    with arcpy.da.UpdateCursor(fc, [lat, long, 'SHAPE@']) as u_cursor:
        counter = 0
        for row in u_cursor:
            centroid = arcpy.PointGeometry(row[2].centroid, orig_crs)
            centroid_nad83 = centroid.projectAs(new_crs)
            row[0] = centroid_nad83.firstPoint.Y
            row[1] = centroid_nad83.firstPoint.X
            u_cursor.updateRow(row)

# arcpy.env.workspace = mgdb
# ecoregions = arcpy.ListFeatureClasses('*', feature_dataset='Ecoregions')
# zones = arcpy.ListFeatureClasses('*', feature_dataset='Spatial_Classifications')
# fcs = ecoregions + zones
#
# for fc in fcs:
#     if 'epanutr3' in fc or 'epawsa9' in fc:
#         print fc
#         add_lat_long(fc)

# 2) populate "states" field
def find_states(fc, state_fc, zone_name=''):
    """Populate *_states field. States fc must have field 'states' with length 255 and state abbreviations within."""
    if zone_name:
        zone_name = zone_name
    else:
        zone_name = os.path.basename(fc)
    states_field = '{}_states'.format(zone_name)
    if arcpy.ListFields(fc, states_field):
        DM.DeleteField(fc, states_field)

    # reverse buffer the states slightly to avoid "D", "I", "J"  situations in "INTERSECT" illustration
    # from graphic examples of ArcGIS join types "Select polygon using polygon" section in Help


    # make a field mapping that gathers all the intersecting states into one new value
    field_list = [f.name for f in arcpy.ListFields(fc) if f.type <> 'OID' and f.type <> 'Geometry']
    field_mapping = arcpy.FieldMappings()
    for f in field_list:
        map = arcpy.FieldMap()
        map.addInputField(fc, f)
        field_mapping.addFieldMap(map)
    map_states = arcpy.FieldMap()
    map_states.addInputField(state_fc, 'states')
    map_states.mergeRule = 'Join'
    map_states.joinDelimiter = ' '
    field_mapping.addFieldMap(map_states)

    # perform join and use output to replace original fc
    spjoin = AN.SpatialJoin(fc, state_fc, 'in_memory/spjoin_intersect', 'JOIN_ONE_TO_ONE',
                            field_mapping=field_mapping, match_option='INTERSECT')
    DM.AlterField(spjoin, 'states', new_field_name=states_field, clear_field_alias=True)
    DM.Delete(fc)
    DM.CopyFeatures(spjoin, fc)
    DM.Delete(spjoin)
#
# fcs = []
# walk = arcpy.da.Walk(mgdb, datatype='FeatureClass')
# for dirpath, dirnames, filenames in walk:
#     for filename in filenames:
#         if 'Ecoregions' in dirpath or 'Spatial_Classifications' in dirpath:
#             if filename != 'state':
#                 fcs.append(os.path.join(dirpath, filename))
#
# for fc in fcs:
#     if 'epanutr3' in fc or 'epawsa9' in fc:
#         print fc
#         find_states(fc, state)


# # 3) new lake buffer layers (maybe some code to refresh all lake related layers in case of changes? does it save time?)
# def update_lake_layers(islandfree_lake_fc):
#     def repair(fc):
#         """Remove circular arcs so that feature class contains only Simple Features and can be used in R/sf."""
#         DM.RepairGeometry(fc)
#         DM.AddField(fc, 'VertexCount', 'LONG')
#         DM.CalculateField(fc, 'VertexCount', '!shape!.pointcount', 'PYTHON')
#         lyr = DM.MakeFeatureLayer(fc, 'lyr')
#         DM.SelectLayerByAttribute(lyr, 'NEW_SELECTION', 'VertexCount < 4')
#         arcpy.Densify_edit(lyr, 'OFFSET', max_deviation='10 Meters')
#         DM.DeleteField(lyr, 'VertexCount')
#         DM.Delete(lyr)
#
#
#
#     def buffer(fc, output_fc, distance):
#         print('buffer {} {}'.format(fc, datetime.now))
#         AN.Buffer(islandfree_lake_fc, output_fc, buffer_distance_or_field=str(distance), line_side='OUTSIDE_ONLY')
#         print('repair {} {}'.format(fc, datetime.now))
#         DM.DeleteField(output_fc, 'ORIG_FID')
#         DM.DeleteField(output_fc, 'BUFF_DIST')
#         repair(output_fc)
#
#     lake100 = islandfree_lake_fc + '_100m'
#     lake500 = islandfree_lake_fc + '_500m'
#     lake1500 = islandfree_lake_fc + '_1500m'
#
#     buffer(islandfree_lake_fc, lake100, 100)
#     buffer(islandfree_lake_fc, lake500, 500)
#     buffer(islandfree_lake_fc, lake1500, 1500)
#
# update_lake_layers(lakes)

# # update Plotting layers
# def update_plotting(mgdb):
#     arcpy.env.workspace = mgdb
#     ecoregions = arcpy.ListFeatureClasses(feature_dataset='Ecoregions')
#     zones = arcpy.ListFeatureClasses(feature_dataset='Spatial_Classifications')
#     fcs = ecoregions + zones

# # Glaciation
GLACIAL_EXTENT = r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\GEO_datadownload_inprogress\DATA_glaciationlatewisc\Pre-processed\lgm_glacial.shp'
# fcs = []
# walk = arcpy.da.Walk(mgdb, datatype='FeatureClass', type='Polygon')
# for dirpath, dirnames, filenames in walk:
#     for filename in filenames:
#         if 'Lakes' in dirpath or 'Spatial_Classifications' in dirpath or 'Ecoregions' in dirpath:
#             fcs.append(os.path.join(dirpath, filename))
#
def calc_glaciation(fc, zone_field, zone_name=''):
    # tab area
    if zone_name:
        zone_name = zone_name
    else:
        zone_name = os.path.basename(fc)
    g_field = '{}_glaciatedlatewisc'.format(zone_name)
    AN.TabulateIntersection(fc, zone_field, GLACIAL_EXTENT, 'in_memory/glacial_tab')
    glacial_pct = {r[0]:r[1] for r in arcpy.da.SearchCursor('in_memory/glacial_tab', [zone_field, 'PERCENTAGE'])}
    DM.AddField(fc, g_field, 'TEXT', field_length=20)
    with arcpy.da.UpdateCursor(fc, [zone_field, g_field]) as u_cursor:
        for row in u_cursor:
            zoneid, glaciation = row
            if zoneid not in glacial_pct:
                glaciation = 'Not_Glaciated'
            else:
                if glacial_pct[zoneid] >=99.99:
                    glaciation = 'Glaciated'
                elif glacial_pct[zoneid] < 0.01:
                    glaciation = 'Not_Glaciated'
                else:
                    glaciation = 'Partially_Glaciated'
            u_cursor.updateRow((zoneid, glaciation))
    DM.Delete('in_memory/glacial_tab')
#
#
# for fc in fcs:
#     if os.path.basename(fc) in ('epanutr4', 'epanutr3', 'epawsa9', 'bailey', 'mlra', 'neon', 'wwf',
#               'LAGOS_US_All_Lakes_1ha', 'LAGOS_US_All_Lakes_1ha_No_Islands', 'LAGOS_US_All_Lakes_1ha_AUSTIN20190520',
#               'state', 'county', 'hu12', 'hu4', 'hu8'):
#         continue
#     else:
#         print fc
#         zone_fields = arcpy.ListFields(fc, '*zoneid') + arcpy.ListFields(fc, 'lagoslakeid')
#         zone_field = zone_fields[0].name
#         calc_glaciation(fc, zone_field)


# # Subsets
# fcs = []
# walk = arcpy.da.Walk(mgdb, datatype='FeatureClass')
# for dirpath, dirnames, filenames in walk:
#     for filename in filenames:
#         if 'Lakes' in dirpath or 'Spatial_Classifications' in dirpath:
#             if filename not in ['state', 'county', 'hu12', 'hu4', 'hu8']:
#                 fcs.append(os.path.join(dirpath, filename))
#
# for fc in fcs:
#     zone_fields = arcpy.ListFields('*zoneid') + arcpy.ListFields('lagoslakeid')
#     zone_field = zone_fields[0].name
#     lagosGIS.subset_overlapping_zones(fc, zone_field, fc + '_grouped')


# # Delete extraneous lake fields
# fcs = []
# walk = arcpy.da.Walk(mgdb, datatype='FeatureClass', type='Polygon')
# for dirpath, dirnames, filenames in walk:
#     for filename in filenames:
#         if 'Lakes' in dirpath:
#             fcs.append(os.path.join(dirpath, filename))
# fcs.remove(r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha')


# # 2019-07-29
# # Need to add some of the zone flags to lakes
# LAGOS_LAKES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\LAGOS_US_All_Lakes_1ha'
# LAND_BORDER =  r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\NonPublished\Derived_Land_Borders'
# COASTLINE = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\NonPublished\TIGER_Coastline'
# STATE_FC = r'C:\Users\smithn78\Documents\ArcGIS\Default.gdb\state_negative_100m_buffer'
#
# def lake_zone_flags():
#     print("multipart")
#     trimmed = LAGOS_LAKES
#     DM.AddField(trimmed, 'multipart', 'TEXT', field_length=1)
#     uCursor_fields = ['multipart', 'SHAPE@']
#     with arcpy.da.UpdateCursor(trimmed, uCursor_fields) as uCursor:
#         for row in uCursor:
#             multipart, shape = row
#
#             # multipart flag calc
#             if shape.isMultipart:
#                 multipart = 'Y'
#             else:
#                 multipart = 'N'
#             row = (multipart, shape)
#             uCursor.updateRow(row)
#
#     print("Edge flags...")
#     # add flag fields
#     DM.AddField(trimmed, 'onlandborder', 'TEXT', field_length=2)
#     DM.AddField(trimmed, 'oncoast', 'TEXT', field_length=2)
#
#     trimmed_lyr = DM.MakeFeatureLayer(trimmed, 'trimmed_lyr')
#     # identify border zones
#     border_lyr = DM.MakeFeatureLayer(LAND_BORDER, 'border_lyr')
#     DM.SelectLayerByLocation(trimmed_lyr, 'INTERSECT', border_lyr)
#     DM.CalculateField(trimmed_lyr, 'onlandborder', "'Y'", 'PYTHON')
#     DM.SelectLayerByAttribute(trimmed_lyr, 'SWITCH_SELECTION')
#     DM.CalculateField(trimmed_lyr, 'onlandborder', "'N'", 'PYTHON')
#
#     # identify coastal zones
#     coastal_lyr = DM.MakeFeatureLayer(COASTLINE, 'coastal_lyr')
#     DM.SelectLayerByLocation(trimmed_lyr, 'INTERSECT', coastal_lyr)
#     DM.CalculateField(trimmed_lyr, 'oncoast', "'Y'", 'PYTHON')
#     DM.SelectLayerByAttribute(trimmed_lyr, 'SWITCH_SELECTION')
#     DM.CalculateField(trimmed_lyr, 'oncoast', "'N'", 'PYTHON')
#
#     print("State assignment...")
#     find_states(trimmed, STATE_FC)
#
# lake_zone_flags()

# # 2019-08-06
# # Code to finalize watersheds
# import arcpy
# import watersheds_toolchain as w
#
# # # add flags
# # w.add_ws_flags()
# # w.add_hr_indicator()
#
# # merge them
# parent = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds'
# output_iws = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\LAGOS_watersheds.gdb\interlake_watersheds'
# output_net = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\LAGOS_watersheds.gdb\network_watersheds'
#
# # w.merge_watersheds(parent, output_iws, 'interlake')
# # w.merge_watersheds(parent, output_net, 'network')
#
# # add lagoslakeid
# master_lakes = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
# permid_lagosid = {r[0]:r[1] for r in arcpy.da.SearchCursor(master_lakes, ['Permanent_Identifier', 'lagoslakeid'])}
# arcpy.AddField_management(output_iws, 'lagoslakeid', 'LONG')
# arcpy.AddField_management(output_net, 'lagoslakeid', 'LONG')
# with arcpy.da.UpdateCursor(output_iws, ['Permanent_Identifier', 'lagoslakeid']) as u_cursor:
#     for row in u_cursor:
#         row[1] = permid_lagosid[row[0]]
#         u_cursor.updateRow(row)
#
# with arcpy.da.UpdateCursor(output_net, ['Permanent_Identifier', 'lagoslakeid']) as u_cursor:
#     for row in u_cursor:
#         row[1] = permid_lagosid[row[0]]
#         u_cursor.updateRow(row)
#
# # de-duplicate, letting the larger watershed be the main one for this lake (keeps watersheds from crossing HU4s)
# import merge_subregion_outputs as submerge
# stored_rules = submerge.store_rules(['Shape_Area'], [1], ["max"])
# submerge.deduplicate(output_iws, stored_rules)
# # If you re-run this code, WARNING: Lake Pontchartrain will need manual fixing. 2019-10-07
# # It would be better to work on the IWS first, then join on Permanent_Identifier AND VPUID to NWS to retain the corresponding
# # polygons. Saving myself the effort today in hopes that I never need to re-run.
####### submerge.deduplicate(output_net, stored_rules)
#
# # add indexes
# arcpy.AddIndex_management(output_iws, 'lagoslakeid', 'IDX_lagoslakeid')
# arcpy.AddIndex_management(output_net, 'lagoslakeid', 'IDX_lagoslakeid')


# # 2019-08-21
# # Need to add some basic flags to the zones along with some shape/lake info
# nws = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\LAGOS_watersheds.gdb\nws'
# ws = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\LAGOS_watersheds.gdb\ws'
# lakes = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
# lake_area_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(lakes, ['lagoslakeid', 'lake_waterarea_ha'])}
#
# try:
#     DM.AddField(ws, 'ws_focallakewaterarea_ha', 'DOUBLE')
#     DM.AddField(ws, 'ws_area_ha', 'DOUBLE')
#     DM.AddField(ws, 'ws_perimeter_m', 'DOUBLE')
# except:
#     pass
#
# fields = ['lagoslakeid', 'ws_focallakewaterarea_ha', 'ws_area_ha', 'ws_perimeter_m', 'SHAPE@']
#
# print('ws')
# with arcpy.da.UpdateCursor(ws, fields) as u_cursor:
#     for row in u_cursor:
#         id, lake_area, area, perim, shape = row
#         lake_area = lake_area_dict[id]
#         area = shape.area / 10000 # convert m to ha
#         perim = shape.length # in correct units already
#         row = (id, lake_area, area, perim, shape)
#         u_cursor.updateRow(row)
#
# try:
#     DM.AddField(nws, 'nws_focallakewaterarea_ha', 'DOUBLE')
#     DM.AddField(nws, 'nws_area_ha', 'DOUBLE')
#     DM.AddField(nws, 'nws_perimeter_m', 'DOUBLE')
# except:
#     pass
# fields = ['lagoslakeid', 'nws_focallakewaterarea_ha', 'nws_area_ha', 'nws_perimeter_m', 'SHAPE@']
#
# print('nws')
# with arcpy.da.UpdateCursor(nws, fields) as u_cursor:
#     for row in u_cursor:
#         id, lake_area, area, perim, shape = row
#         lake_area = lake_area_dict[id]
#         area = shape.area / 10000 # convert m to ha
#         perim = shape.length # in correct units already
#         row = (id, lake_area, area, perim, shape)
#         u_cursor.updateRow(row)
#
# # and then I need to get the zones into the MGD and add their zone flags
#
# # 2019-08-22
# # add Kath watershed flags
# nws = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\LAGOS_watersheds.gdb\nws'
# ws = r'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds\LAGOS_watersheds.gdb\ws'
# kath_nws =  r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\Kath_GIS_work\LAGOS_watersheds.gdb\network_watersheds_mbgconvexhull'
# kath_ws = r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\Kath_GIS_work\LAGOS_watersheds.gdb\interlake_watersheds_mbgconvexhull'
#
# try:
#     DM.AddField(ws, 'ws_mbgconhull_length_m', 'FLOAT')
#     DM.AddField(ws, 'ws_mbgconhull_width_m', 'FLOAT')
#     DM.AddField(ws, 'ws_mbgconhull_orientation_deg', 'FLOAT')
#     DM.AddField(ws, 'ws_meanwidth_m', 'FLOAT')
# except:
#     pass
# new_fields = ['ws_mbgconhull_length_m', 'ws_mbgconhull_width_m', 'ws_mbgconhull_orientation_deg', 'ws_meanwidth_m']
#
# kath_fields = ['lagoslakeid', 'MBG_Length', 'MBG_Width', 'MBG_Orientation']
# kath_dict = {r[0]: r[1:] for r in arcpy.da.SearchCursor(kath_ws, kath_fields)}
#
# with arcpy.da.UpdateCursor(ws, ['ws_lagoslakeid', 'ws_area_ha'] + new_fields) as u_cursor:
#     for row in u_cursor:
#         id, area, l, w, o, mw = row
#         kl, kw, ko = kath_dict[id]
#         l = kl
#         w = kw
#         o = ko
#         mw = (10000 * area)/l
#         row = (id, area, l, w, o, mw)
#         u_cursor.updateRow(row)
#
# try:
#     DM.AddField(nws, 'nws_mbgconhull_length_m', 'FLOAT')
#     DM.AddField(nws, 'nws_mbgconhull_width_m', 'FLOAT')
#     DM.AddField(nws, 'nws_mbgconhull_orientation_deg', 'FLOAT')
#     DM.AddField(nws, 'nws_meanwidth_m', 'FLOAT')
# except:
#     pass
# new_fields = ['nws_mbgconhull_length_m', 'nws_mbgconhull_width_m', 'nws_mbgconhull_orientation_deg', 'nws_meanwidth_m']
#
# kath_fields = ['lagoslakeid', 'MBG_Length', 'MBG_Width', 'MBG_Orientation']
# kath_dict = {r[0]: r[1:] for r in arcpy.da.SearchCursor(kath_nws, kath_fields)}
#
# with arcpy.da.UpdateCursor(nws, ['nws_lagoslakeid', 'nws_area_ha'] + new_fields) as u_cursor:
#     for row in u_cursor:
#         id, area, l, w, o, mw = row
#         kl, kw, ko = kath_dict[id]
#         l = kl
#         w = kw
#         o = ko
#         mw = (10000 * area)/l
#         row = (id, area, l, w, o, mw)
#         u_cursor.updateRow(row)
#


# # 2019-08-22
# # add zoneids to the lakes
# lakes_fc =  r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha_points'
# mgdb = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb'
#
# zones = ['hu12', 'hu8', 'hu4', 'county', 'state', 'epanutr4', 'wwf', 'mlra', 'bailey', 'neon']
#
# for z in zones:
#     print z
#     zone = os.path.join(mgdb, z)
#     zoneid = '{}_zoneid'.format(z)
#     if not arcpy.ListFields(lakes_fc, zoneid):
#         DM.AddField(lakes_fc, zoneid, 'TEXT', '20')
#
#     join_fc = arcpy.SpatialJoin_analysis(lakes_fc, zone, 'in_memory/join_fc', 'JOIN_ONE_TO_ONE', match_option='INTERSECT')
#     zoneid1 = '{}_1'.format(zoneid)
#     join_missing = arcpy.Select_analysis(join_fc, 'in_memory/join_missing', '{} is null'.format(zoneid1)) # joined always gets _1 suffix bc same name in lakes
#     arcpy.DeleteField_management(join_missing, zoneid1)
#     update_vals = {}
#     # if there was no INTERSECT zone, find the CLOSEST zone
#     count_missing = int(DM.GetCount(join_missing).getOutput(0))
#     print(count_missing)
#     if count_missing > 0:
#         print("Using CLOSEST join...")
#         join_fc2 = arcpy.SpatialJoin_analysis(join_missing, zone, 'in_memory/join_fc2', 'JOIN_ONE_TO_ONE',
#                                               match_option='CLOSEST')
#         update_vals = {r[0]:r[1] for r in arcpy.da.SearchCursor(join_fc2, ['lagoslakeid', zoneid1])}
#
#     # make a dict from combining the INTERSECT and CLOSEST results
#     zone_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(join_fc, ['lagoslakeid', zoneid1])}
#     for k, v in zone_dict.items():
#         if not v:
#             zone_dict[k] = update_vals[k]
#
#     with arcpy.da.UpdateCursor(lakes_fc, ['lagoslakeid', zoneid]) as u_cursor:
#         for row in u_cursor:
#             row[1] = zone_dict[row[0]]
#             u_cursor.updateRow(row)
#
#     DM.Delete('in_memory')


# 2019-08-29
# Add templinkid to LAGOS_limno_spatialized.gdb
# import arcpy
# gdb = r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\Lake_Georeferencing\LAGOS_limno_spatialized.gdb'
# arcpy.env.workspace = gdb
# fcs = arcpy.ListFeatureClasses(('*_linked'))
#
def add_templinkid(fc):
    try:
        arcpy.AddField_management(fc, 'templinkid', 'TEXT', field_length=255)
    except:
        pass
    with arcpy.da.UpdateCursor(fc, 'templinkid') as cursor:
        counter = 1
        for row in cursor:
            row[0] = '{}-{:05d}'.format(fc, counter)
            counter += 1
            cursor.updateRow(row)
#
# for fc in fcs:
#     print(fc)
#     add_templinkid(fc)
#     add_templinkid(fc)

# # 2019-11-08
# # re-calculate zoneids for the lakes
# lakes_fc =  r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha_points'
# mgdb = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb'
#
# # zones = ['hu12', 'hu8', 'hu4', 'county', 'state', 'epanutr4', 'wwf', 'mlra', 'bailey', 'neon']
# zones = ['omernik3', 'epanutr']
#
# for z in zones:
#     print z
#     zone = os.path.join(mgdb, z)
#     zoneid = '{}_zoneid'.format(z)
#     if not arcpy.ListFields(lakes_fc, zoneid):
#         DM.AddField(lakes_fc, zoneid, 'TEXT', '20')
#
#     join_fc = arcpy.SpatialJoin_analysis(lakes_fc, zone, 'in_memory/join_fc', 'JOIN_ONE_TO_ONE', match_option='INTERSECT')
#     zoneid1 = '{}_1'.format(zoneid)
#     join_missing = arcpy.Select_analysis(join_fc, 'in_memory/join_missing', '{} is null'.format(zoneid1)) # joined always gets _1 suffix bc same name in lakes
#     arcpy.DeleteField_management(join_missing, zoneid1)
#     update_vals = {}
#
#     # if there was no INTERSECT zone, find the CLOSEST zone
#     count_missing = int(DM.GetCount(join_missing).getOutput(0))
#     print(count_missing)
#     if count_missing > 0:
#         print("Using CLOSEST join...")
#         join_fc2 = arcpy.SpatialJoin_analysis(join_missing, zone, 'in_memory/join_fc2', 'JOIN_ONE_TO_ONE',
#                                               match_option='CLOSEST')
#         update_vals = {r[0]:r[1] for r in arcpy.da.SearchCursor(join_fc2, ['lagoslakeid', zoneid1])}
#
#     # make a dict from combining the INTERSECT and CLOSEST results
#     zone_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(join_fc, ['lagoslakeid', zoneid1])}
#     for k, v in zone_dict.items():
#         if not v:
#             zone_dict[k] = update_vals[k]
#
#     with arcpy.da.UpdateCursor(lakes_fc, ['lagoslakeid', zoneid]) as u_cursor:
#         for row in u_cursor:
#             row[1] = zone_dict[row[0]]
#             u_cursor.updateRow(row)
#
#     DM.Delete('in_memory')

# # update the main lakes layer
# lakes_poly = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
# lakes_point = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha_points'
#
# #zones = ['hu12', 'hu8', 'hu4', 'county', 'state', 'epanutr4', 'wwf', 'mlra', 'bailey', 'neon']
# zones = ['omernik3', 'epanutr']
# zoneids = ['{}_zoneid'.format(z) for z in zones]
#
# point_dict = {r[0]:r[1:] for r in arcpy.da.SearchCursor(lakes_point, ['lagoslakeid'] + zoneids)}
#
# for z in zoneids:
#     if not arcpy.ListFields(lakes_poly, z):
#         DM.AddField(lakes_poly, z, 'TEXT', field_length=20)
# with arcpy.da.UpdateCursor(lakes_poly, ['lagoslakeid'] + zoneids) as u_cursor:
#     for row in u_cursor:
#         row[1:] = point_dict[row[0]]
#         u_cursor.updateRow(row)

# # 2020-04-30 Try the lake state thing again, I just set the old one to lake_state_OLD20200430
# # for some reason last time it missed some lakes
#
# print('lake states')
# lakes_fc = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
# states = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\state'
# find_states(lakes_fc, states, zone_name='lake')

# 2020-05-05 Try the lake state thing again, I just set the old one to lake_state_OLD20200430
# for some reason last time it missed some lakes
#
# print('ws states')
# ws = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\Spatial_Classifications\ws'
# states = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\state'
# find_states(ws, states, zone_name='ws')