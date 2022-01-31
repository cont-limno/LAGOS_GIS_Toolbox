# filename: zone_prep.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (NOT in ArcGIS Toolbox)

import os
import arcpy
from arcpy import analysis as AN, management as DM


def add_lat_lon(fc, zone_name=''):
    """Add fields for lat and long, per LAGOS naming standard. Only works when fc path is short (use env.workspace.)"""
    if not zone_name:
        zone_name = fc
    lat = '{}_lat_decdeg'.format(zone_name)
    lon = '{}_lon_decdeg'.format(zone_name)
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

def inusa_pct(zone_fc, zoneid, states_fc, zone_name=''):
    DM.AddField(zone_fc, '{}_inusa_pct'.format(zone_name), 'DOUBLE')
    # percent in USA
    arcpy.AddMessage('Tabulating intersection...')
    arcpy.TabulateIntersection_analysis(zone_fc, zoneid, states_fc, 'in_memory/tabarea')

    # round to 2 digits and don't let values exceed 100
    inusa_dict = {r[0]:min(round(r[1],2), 100)
                  for r in arcpy.da.SearchCursor('in_memory/tabarea', [zoneid, 'PERCENTAGE'])}

    with arcpy.da.UpdateCursor(zone_fc, [zoneid, 'inusa_pct']) as u_cursor:
        for row in u_cursor:
            row[1] = inusa_dict[row[0]]
            u_cursor.updateRow(row)

    DM.Delete('in_memory/tabarea')