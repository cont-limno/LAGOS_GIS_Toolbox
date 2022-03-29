# filename: flatten_overlapping_zones.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)

import os
import arcpy
from arcpy import management as DM
from arcpy import analysis as AN


def flatten(zone_fc, zone_field, output_fc, output_table, cluster_tolerance='3 Meters'):
    """
    Converts overlapping zone polygons into non-overlapping regions (first output) and provides a table of identifiers
    to link between input and output polygons (second output).
    :param zone_fc: A polygon feature class containing overlapping zones
    :param zone_field: The unique identifier for each zone
    :param output_fc: The output feature class location
    :param output_table: The output table location
    :param cluster_tolerance: Cluster tolerance passed to Union function (The minimum distance separating all feature
    coordinates (nodes and vertices) as well as the distance a coordinate can move in X or Y (or both).)
    :return: Output feature class path
    """

    # Set-up workspace and naming conventions
    orig_env = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'

    objectid = [f.name for f in arcpy.ListFields(zone_fc) if f.type == 'OID'][0]
    zoneid_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(zone_fc, [objectid, zone_field])}
    zone_field_type = [f.type for f in arcpy.ListFields(zone_fc, zone_field)][0]
    fid1 = 'FID_{}'.format(os.path.basename(zone_fc))
    flat_zoneid = 'flat{}'.format(zone_field)
    flat_zoneid_prefix = 'flat{}_'.format(zone_field.replace('_zoneid', ''))

    # Self-union with FID_Only (A). This step identifies overlapping regions and creates a new feature for them.
    arcpy.AddMessage("Splitting overlaps in polygons...")
    self_union = AN.Union([zone_fc], 'self_union', 'ONLY_FID', cluster_tolerance=cluster_tolerance)

    # Delete features with null geometry. Some kind of geometry repair is commonly helpful following a Union analysis.
    arcpy.AddMessage("Repairing self-union geometries...")
    DM.RepairGeometry(self_union, 'DELETE_NULL')

    # Find Identical by Shape (B)
    if arcpy.Exists('identical_shapes'):
        DM.Delete('identical_shapes') # causes failure in FindIdentical even when overwrite is allowed
    identical_shapes = DM.FindIdentical(self_union, 'identical_shapes', 'Shape')

    # Join A to B and calc flat[zone]_zoneid = FEAT_SEQ (C)
    DM.AddField(self_union, flat_zoneid, 'TEXT', field_length=20)
    union_oid = [f.name for f in arcpy.ListFields(self_union) if f.type == 'OID'][0]
    identical_shapes_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(identical_shapes, ['IN_FID', 'FEAT_SEQ'])}
    with arcpy.da.UpdateCursor(self_union, [union_oid, flat_zoneid]) as u_cursor:
        for row in u_cursor:
            row[1] = '{}{}'.format(flat_zoneid_prefix, identical_shapes_dict[row[0]])
            u_cursor.updateRow(row)

    # Add the original zone ids and save to table (E)
    arcpy.AddMessage("Assigning temporary IDs to split polygons...")
    unflat_table = DM.CopyRows(self_union, 'unflat_table')
    DM.AddField(unflat_table, zone_field, zone_field_type)  # default text length of 50 is fine if needed
    with arcpy.da.UpdateCursor(unflat_table, [fid1, zone_field]) as u_cursor:
        for row in u_cursor:
            row[1] = zoneid_dict[row[0]]  # assign zone id
            u_cursor.updateRow(row)

    # Delete Identical (C) (save as flat[zone])
    with arcpy.da.UpdateCursor(self_union, 'OID@') as cursor:
        visited = []
        for row in cursor:
            feat_seq = identical_shapes_dict[row[0]]
            if feat_seq in visited:
                cursor.deleteRow()
            visited.append(feat_seq)

    DM.DeleteField(self_union, fid1)
    DM.DeleteField(unflat_table, fid1)

    # save outputs
    output_fc = DM.CopyFeatures(self_union, output_fc)
    output_table = DM.CopyRows(unflat_table, output_table)

    # cleanup
    for item in [self_union, identical_shapes, unflat_table]:
        DM.Delete(item)
    arcpy.env.workspace = orig_env

    return output_fc


def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    output_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    cluster_tolerance = arcpy.GetParameterAsText(4)
    flatten(zone_fc, zone_field, output_fc, output_table, cluster_tolerance)


if __name__ == '__main__':
    main()
