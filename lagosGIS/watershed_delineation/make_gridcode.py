# filename: make_gridcode.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import os
import arcpy
import lagosGIS


def make_gridcode(nhd_gdb, output_table):
    """Add lakes to gridcode table and save the result as a new table.

    Only lakes over 0.009 sq. km. in area that match the LAGOS lake filter will be added.The features added will be
    slightly more than those that have watersheds created (more inclusive filter) to allow for inadequate precision
    found in the AreaSqKm field.

    :param nhd_gdb: The NHDPlus HR geodatabase containing the NHDPlusNHDPlusIDGridCode table to be updated
    :param output_table: A new table that contains the contents of NHDPlusNHDPlusIDGridCode,
    plus new rows for waterbodies
    :return: ArcGIS Result object for output_table

    """
    # setup
    from arcpy import management as DM
    vpuid = nhd_gdb[-12:-8]
    nhd_waterbody_fc = os.path.join(nhd_gdb, 'NHDWaterbody')
    nhd_flowline_fc = os.path.join(nhd_gdb, 'NHDFlowline')
    eligible_clause = 'AreaSqKm > 0.009 AND FCode IN {}'.format(lagosGIS.LAGOS_FCODE_LIST)

    # make new table
    result = DM.CreateTable(os.path.dirname(output_table), os.path.basename(output_table))

    DM.AddField(result, 'NHDPlusID', 'DOUBLE')  # dummy field for alignment with HR gridcode table
    DM.AddField(result, 'SourceFC', 'TEXT', field_length=20)
    DM.AddField(result, 'VPUID', 'TEXT', field_length=8)
    DM.AddField(result, 'GridCode', 'LONG')
    DM.AddField(result, 'Permanent_Identifier', 'TEXT', field_length=40)

    # get IDs to be added
    flow_permids = [r[0] for r in arcpy.da.SearchCursor(nhd_flowline_fc, ['Permanent_Identifier'])]
    wb_permids = [r[0] for r in arcpy.da.SearchCursor(nhd_waterbody_fc, ['Permanent_Identifier'], eligible_clause)]

    # start with the next highest grid code
    gridcode = 1
    i_cursor = arcpy.da.InsertCursor(result, ['NHDPlusID', 'SourceFC', 'GridCode', 'VPUID', 'Permanent_Identifier'])

    # insert new rows with new grid codes
    for permid in flow_permids:
        sourcefc = 'NHDFlowline'
        new_row = (None, sourcefc, gridcode, vpuid, permid)
        i_cursor.insertRow(new_row)
        gridcode += 1
    for permid in wb_permids:
        sourcefc = 'NHDWaterbody'
        new_row = (None, sourcefc, gridcode, vpuid, permid)
        i_cursor.insertRow(new_row)
        gridcode += 1
    del i_cursor

    return result


def main():
    nhd_gdb = arcpy.GetParameterAsText(0)
    output_table = arcpy.GetParameterAsText(1)
    make_gridcode(nhd_gdb, output_table)


if __name__ == "__main__":
    main()