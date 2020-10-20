# filename: flatten_overlaps.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)
# status: working, tested in Beta

import os
import arcpy
from arcpy import management as DM
from arcpy import analysis as AN


def flatten_overlaps(zone_fc, zone_field, output_fc, output_table, cluster_tolerance=' 3 Meters'):
    orig_env = arcpy.env.workspace
    arcpy.env.workspace = 'in_memory'

    objectid = [f.name for f in arcpy.ListFields(zone_fc) if f.type == 'OID'][0]
    zone_type = [f.type for f in arcpy.ListFields(zone_fc, zone_field)][0]
    fid1 = 'FID_{}'.format(os.path.basename(zone_fc))
    flat_zoneid = 'flat{}'.format(zone_field)
    flat_zoneid_prefix = 'flat{}_'.format(zone_field.replace('_zoneid', ''))

    # Union with FID_Only (A)
    arcpy.AddMessage("Splitting overlaps in polygons...")
    zoneid_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(zone_fc, [objectid, zone_field])}
    self_union = AN.Union([zone_fc], 'self_union', 'ONLY_FID', cluster_tolerance=cluster_tolerance)

    # #If you don't run this section, Find Identical fails with error 999999. Seems to have to do with small slivers
    # #having 3 vertices and/or only circular arcs in the geometry.
    arcpy.AddMessage("Repairing self-union geometries...")
    # DM.AddGeometryAttributes(self_union, 'POINT_COUNT; AREA')
    # union_fix = DM.MakeFeatureLayer(self_union, 'union_fix', where_clause='PNT_COUNT <= 10 OR POLY_AREA < 5000')
    # arcpy.Densify_edit(union_fix, 'DISTANCE', distance = '1 Meters', max_deviation='1 Meters')  # selection ON, edits self_union disk
    DM.RepairGeometry(self_union, 'DELETE_NULL')  # eliminate empty geoms. selection ON, edits self_union disk
    # for field in ['PNT_COUNT', 'POLY_AREA']:
    #     DM.DeleteField(self_union, field)

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
    DM.AddField(unflat_table, zone_field, zone_type)  # default text length of 50 is fine if needed
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
    flatten_overlaps(zone_fc, zone_field, output_fc, output_table, cluster_tolerance)

if __name__ == '__main__':
    main()