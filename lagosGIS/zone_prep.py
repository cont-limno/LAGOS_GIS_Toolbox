import os
import arcpy
from arcpy import analysis as AN, management as DM


def calc_glaciation(fc, glacial_extent_fc, zone_field, zone_name=''):
    # tab area
    if zone_name:
        zone_name = zone_name
    else:
        zone_name = os.path.basename(fc)
    g_field = '{}_glaciatedlatewisc'.format(zone_name)
    AN.TabulateIntersection(fc, zone_field, glacial_extent_fc, 'in_memory/glacial_tab')
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


def add_lat_lon(fc):
    """Add fields for lat and long, per LAGOS naming standard. Only works when fc path is short (use env.workspace.)"""
    lat = '{}_lat_decdeg'.format(fc)
    lon = '{}_lon_decdeg'.format(fc)
    if not arcpy.ListFields(fc, lat):
        DM.AddField(fc, lat, 'DOUBLE')
    if not arcpy.ListFields(fc, lon):
        DM.AddField(fc, lon, 'DOUBLE')
    orig_crs = arcpy.SpatialReference(5070)
    new_crs = arcpy.SpatialReference(4326)  # NAD83

    with arcpy.da.UpdateCursor(fc, [lat, lon, 'SHAPE@']) as u_cursor:
        for row in u_cursor:
            centroid = arcpy.PointGeometry(row[2].centroid, orig_crs)
            centroid_nad83 = centroid.projectAs(new_crs)
            row[0] = centroid_nad83.firstPoint.Y
            row[1] = centroid_nad83.firstPoint.X
            u_cursor.updateRow(row)


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