# filename: spatial_divisions_processing.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (NOT in ArcGIS Toolbox)

import os
import arcpy
from arcpy import analysis as AN, management as DM


def add_lat_lon(fc, zone_name=''):
    """
    Add latitude and longitude (centroid) fields, per LAGOS naming standard. Only works when fc path is short
    (use env.workspace.)
    :param fc: Zone feature class
    :param zone_name: (Optional) Zone shortname to use as prefix for lat and lon fields
    :return: None
    """
    if not zone_name:
        zone_name = fc
    lat = '{}_lat_decdeg'.format(zone_name)
    lon = '{}_lon_decdeg'.format(zone_name)
    if not arcpy.ListFields(fc, lat):
        DM.AddField(fc, lat, 'DOUBLE')
    if not arcpy.ListFields(fc, lon):
        DM.AddField(fc, lon, 'DOUBLE')
    orig_crs = arcpy.SpatialReference(5070) # Albers USGS
    new_crs = arcpy.SpatialReference(4326)  # NAD83

    with arcpy.da.UpdateCursor(fc, [lat, lon, 'SHAPE@']) as u_cursor:
        for row in u_cursor:
            centroid = arcpy.PointGeometry(row[2].centroid, orig_crs)
            centroid_nad83 = centroid.projectAs(new_crs)
            row[0] = centroid_nad83.firstPoint.Y
            row[1] = centroid_nad83.firstPoint.X
            u_cursor.updateRow(row)


def find_states(zones_fc, state_fc, zone_name=''):
    """
    Populate *_states field in input zones feature class (modifies original. States fc must have field 'states' with
    length 255 and state abbreviations within.
    :param zones_fc: Zones polygon feature class
    :param state_fc: Polygon feature class containing U.S. geometry and field "states" with length 255 and state
    abbreviations within
    :param zone_name: (Optional) If the feature class is not named with the LAGOS-US zone shortname, provide a zone
    prefix to add to output "*_states" field
    :return: None
    """

    # Setup names
    if zone_name:
        zone_name = zone_name
    else:
        zone_name = os.path.basename(zones_fc)
    states_field = '{}_states'.format(zone_name)
    if arcpy.ListFields(zones_fc, states_field):
        DM.DeleteField(zones_fc, states_field)

    # Make a field mapping that gathers all the intersecting states into one new value separated by space
    field_list = [f.name for f in arcpy.ListFields(zones_fc) if f.type <> 'OID' and f.type <> 'Geometry']
    field_mapping = arcpy.FieldMappings()
    for f in field_list:
        map = arcpy.FieldMap()
        map.addInputField(zones_fc, f)
        field_mapping.addFieldMap(map)
    map_states = arcpy.FieldMap()
    map_states.addInputField(state_fc, 'states')
    map_states.mergeRule = 'Join'
    map_states.joinDelimiter = ' '
    field_mapping.addFieldMap(map_states)

    # Perform join and use output to replace original fc
    spjoin = AN.SpatialJoin(zones_fc, state_fc, 'in_memory/spjoin_intersect', 'JOIN_ONE_TO_ONE',
                            field_mapping=field_mapping, match_option='INTERSECT')
    DM.AlterField(spjoin, 'states', new_field_name=states_field, clear_field_alias=True)
    DM.Delete(zones_fc)
    DM.CopyFeatures(spjoin, zones_fc)
    DM.Delete(spjoin)


def inusa_pct(zone_fc, zoneid, states_fc, zone_name=''):
    """
    Calculates percentage of zone that is within the U.S. boundaries. Modifies original zones feature class input.
    :param zone_fc: Zones feature class
    :param zoneid: Unique identifier for each zone
    :param states_fc: Polygon feature class containing U.S. states
    :param zone_name: (Optional) If the feature class is not named with the LAGOS-US zone shortname, provide a zone
    prefix to add to output "*_states" field
    :return: None
    """
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