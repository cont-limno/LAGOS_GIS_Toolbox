import os
import arcpy
from arcpy import management as DM
from arcpy import analysis as AN
import make_lagos_lakes


# Calculate zoneids for the lakes
LAKES_POINT = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\Lakes\LAGOS_US_All_Lakes_1ha_points'
LAKES_POLY = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\Lakes\LAGOS_US_All_Lakes_1ha'
MGDB = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb'
STATES = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.7.gdb\state'
GLACIAL_EXTENT = r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\GEO_datadownload_inprogress\DATA_glaciationlatewisc\Pre-processed\lgm_glacial.shp'
LAND_BORDER =  r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\NonPublished\Derived_Land_Borders'
COASTLINE = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\NonPublished\TIGER_Coastline'
STATES_NEGATIVE_BUFFER = r'C:\Users\smithn78\Documents\ArcGIS\Default.gdb\state_negative_100m_buffer'

def add_zoneids_to_lakes(lakes_points_fc, lakes_poly, mgdb):
    zones = ['hu12', 'hu8', 'hu4', 'county', 'state', 'epanutr4', 'wwf', 'mlra', 'bailey', 'neon', 'omernik3', 'epanutr']
    for z in zones:
        print z
        zone = os.path.join(mgdb, z)
        zoneid = '{}_zoneid'.format(z)
        if not arcpy.ListFields(lakes_points_fc, zoneid):
            DM.AddField(lakes_points_fc, zoneid, 'TEXT', '20')

        join_fc = arcpy.SpatialJoin_analysis(lakes_points_fc, zone, 'in_memory/join_fc', 'JOIN_ONE_TO_ONE', match_option='INTERSECT')
        zoneid1 = '{}_1'.format(zoneid)
        join_missing = arcpy.Select_analysis(join_fc, 'in_memory/join_missing', '{} is null'.format(zoneid1)) # joined always gets _1 suffix bc same name in lakes
        arcpy.DeleteField_management(join_missing, zoneid1)
        update_vals = {}

        # if there was no INTERSECT zone, find the CLOSEST zone
        count_missing = int(DM.GetCount(join_missing).getOutput(0))
        print(count_missing)
        if count_missing > 0:
            print("Using CLOSEST join...")
            join_fc2 = arcpy.SpatialJoin_analysis(join_missing, zone, 'in_memory/join_fc2', 'JOIN_ONE_TO_ONE',
                                                  match_option='CLOSEST')
            update_vals = {r[0]:r[1] for r in arcpy.da.SearchCursor(join_fc2, ['lagoslakeid', zoneid1])}

        # make a dict from combining the INTERSECT and CLOSEST results
        zone_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(join_fc, ['lagoslakeid', zoneid1])}
        for k, v in zone_dict.items():
            if not v:
                zone_dict[k] = update_vals[k]

        with arcpy.da.UpdateCursor(lakes_points_fc, ['lagoslakeid', zoneid]) as u_cursor:
            for row in u_cursor:
                row[1] = zone_dict[row[0]]
                u_cursor.updateRow(row)

        DM.Delete('in_memory')

    # update the main lakes layer
    zoneids = ['{}_zoneid'.format(z) for z in zones]
    point_dict = {r[0]:r[1:] for r in arcpy.da.SearchCursor(lakes_points_fc, ['lagoslakeid'] + zoneids)}

    for z in zoneids:
        if not arcpy.ListFields(lakes_poly, z):
            DM.AddField(lakes_poly, z, 'TEXT', field_length=20)
    with arcpy.da.UpdateCursor(lakes_poly, ['lagoslakeid'] + zoneids) as u_cursor:
        for row in u_cursor:
            row[1:] = point_dict[row[0]]
            u_cursor.updateRow(row)


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

# Need to add some of the zone flags to lakes
def lake_zone_flags():
    print("multipart")
    trimmed = LAKES_POLY
    DM.AddField(trimmed, 'multipart', 'TEXT', field_length=1)
    uCursor_fields = ['multipart', 'SHAPE@']
    with arcpy.da.UpdateCursor(trimmed, uCursor_fields) as uCursor:
        for row in uCursor:
            multipart, shape = row

            # multipart flag calc
            if shape.isMultipart:
                multipart = 'Y'
            else:
                multipart = 'N'
            row = (multipart, shape)
            uCursor.updateRow(row)

    print("Edge flags...")
    # add flag fields
    DM.AddField(trimmed, 'onlandborder', 'TEXT', field_length=2)
    DM.AddField(trimmed, 'oncoast', 'TEXT', field_length=2)

    trimmed_lyr = DM.MakeFeatureLayer(trimmed, 'trimmed_lyr')
    # identify border zones
    border_lyr = DM.MakeFeatureLayer(LAND_BORDER, 'border_lyr')
    DM.SelectLayerByLocation(trimmed_lyr, 'INTERSECT', border_lyr)
    DM.CalculateField(trimmed_lyr, 'onlandborder', "'Y'", 'PYTHON')
    DM.SelectLayerByAttribute(trimmed_lyr, 'SWITCH_SELECTION')
    DM.CalculateField(trimmed_lyr, 'onlandborder', "'N'", 'PYTHON')

    # identify coastal zones
    coastal_lyr = DM.MakeFeatureLayer(COASTLINE, 'coastal_lyr')
    DM.SelectLayerByLocation(trimmed_lyr, 'INTERSECT', coastal_lyr)
    DM.CalculateField(trimmed_lyr, 'oncoast', "'Y'", 'PYTHON')
    DM.SelectLayerByAttribute(trimmed_lyr, 'SWITCH_SELECTION')
    DM.CalculateField(trimmed_lyr, 'oncoast', "'N'", 'PYTHON')

    print("State assignment...")
    find_states(trimmed, STATES_NEGATIVE_BUFFER)


#---MAKE THE LAKES AND ADD ALL FIELDS-----------------------------------------------------------------------------------
# lots of paths specific to LAGOS workstation, this line included as a pointer to the log of how we created the lakes
# layer, can't be easily re-run without heavy modifications
make_lagos_lakes.make_lagos_lakes()

# lake points and pseudo-centroids for lat long
DM.FeatureToPoint(LAKES_POLY, LAKES_POINT, 'INSIDE')
# TODO: Used calculate geometry with NAD83 in GUI, convert


# FLAGS, ZONEIDS, STATES
lake_zone_flags()
add_zoneids_to_lakes(LAKES_POINT, LAKES_POLY, MGDB)
find_states(LAKES_POLY, STATES, zone_name='lake')

# GLACIATION
calc_glaciation(LAKES_POLY, 'lagoslakeid', 'lake')
# replace lakes that are "partially glaciated" to be just "glaciated" since compared to zones they are small and
# that makes more sense
with arcpy.da.UpdateCursor(LAKES_POLY, ['lake_glaciatedlatewisc']) as cursor:
    for row in cursor:
        if row[0] == 'Partially_Glaciated':
            row[0] = 'Glaciated'
    cursor.updateRow(row)



