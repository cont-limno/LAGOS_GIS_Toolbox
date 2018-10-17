import arcpy

def build_from_to_table(network_fc, out_gdb):
    network_cursor = arcpy.da.SearchCursor(network_fc, ['OID','SHAPE@XY'])
    nodes = [(row[0], row[-1].firstPoint, row[-1].lastPoint) for row in network_cursor]

    nodes = arcpy.CreateFeatureclass_management(out_gdb, 'Nodes', 'MULTIPOINT')
    arcpy.AddField_management(nodes, 'FID')
    boundary_cursor = arcpy.da.InsertCursor(nodes, )