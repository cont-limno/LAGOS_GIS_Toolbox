import os
from arcpy import management as DM
import arcpy

def assign_catchments_to_lakes(nhdplus_gdb, output_fc):
    # copy
    arcpy.env.workspace = 'in_memory'
    nhd_cat = os.path.join(nhdplus_gdb, 'NHDPlusCatchment')
    nhd_flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
    nhd_wb = os.path.join(nhdplus_gdb, 'NHDWaterbody')
    nhd_cat_copy = DM.CopyFeatures(nhd_cat, 'nhd_cat_copy')
    DM.AddField(nhd_cat_copy, 'Lake_Permanent_Identifier', field_type = 'TEXT', length = 40)

    # Add Join 2X to get artificial flowline to lake mapping
    # if this doesn't work it's because you need a layer for nhd_flowline
    DM.AddJoin(nhd_cat_copy, 'NHDPlusID', nhd_flowline, 'NHDPlusID')

    # and if this doesn't work it's because of the aliases
    DM.AddJoin(nhd_cat_copy, 'NHDFlowline.WBArea_Permanent_Identifier', nhd_wb, 'Permanent_Identifier')


    # Copy Permanent_Identifier to new field
    DM.CalculateField(nhd_cat_copy, 'nhd_cat_copy.Lake_Permanent_Identifier', '!NHDWaterbody.Permanent_Identifier!')

    # remove joins
    DM.RemoveJoin(nhd_cat_copy)

    # join to sinks to get sink to lake mapping
    DM.AddJoin(nhd_cat_copy, 'NHDPlusID', nhd_wb, 'NHDPlusID')

    # if new id is null, then copy the perm id
    cursor = arcpy.UpdateCursor(nhd_cat_copy, [
        'nhd_cat_copy.Lake_Permanent_Identifier',
        'NHDWaterbody.Permanent_Identifier'])
    for row in cursor:
        new_id, wb_id = row
        if new_id is None:
            new_id = wb_id
        cursor.updateRow(new_id, wb_id)

    # remove all joins
    DM.RemoveJoin(nhd_cat_copy)

    # merge catchments for lakes
    DM.Dissolve(nhd_cat_copy, output_fc, 'Lake_Permanent_Identifier')