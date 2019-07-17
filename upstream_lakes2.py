#-------------------------------------------------------------------------------
# Name:        upstream_lakes
# Purpose:
#
# Author:      smithn78
#
# Created:     17/07/2019


#-------------------------------------------------------------------------------
import os
import arcpy
import nhdplushr_tools as nt

def upstream_lakes(nhd_gdb, output_table, unique_id = 'lagoslakeid'):
    #define paths in nhd geodatabase
    network = nt.NHDNetwork(nhd_gdb)
    # nhd_waterbody = os.path.join(nhd_gdb, 'NHDWaterbody')
    nhd_junctions = os.path.join(nhd_gdb, 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET')

    arcpy.env.workspace = 'in_memory'

    arcpy.AddMessage('Preparing layers and fields for calculations....')
    # arcpy.MakeFeatureLayer_management(nhd_junctions, 'junctions')


    # select only lakes as defined in our project: waterbodies with one of these
    # types and greater than 4ha, and certain reservoirs greater than 10ha
    # These filters should be aligned with LakeConnectivity (they currently are)
    gte_1ha_lakes_query = ''' "AreaSqKm" >=0.009 AND "FType" IN (390, 436) '''
    gte_4ha_lakes_query = ''' "AreaSqKm" >=0.04 AND "FType" IN (390, 436) '''
    gte_10ha_lakes_query = ''' "AreaSqKm" >=0.1 AND "FType" IN (390, 436) '''

    # make a list of each
    gte_1ha_lakes_list = [row[0] for row in arcpy.da.SearchCursor(
        network.waterbody, 'Permanent_Identifier', gte_1ha_lakes_query) if row[0]]
    gte_1ha_lakes_set = set(gte_1ha_lakes_list)
    gte_4ha_lakes_set = {row[0] for row in arcpy.da.SearchCursor(
        network.waterbody, 'Permanent_Identifier', gte_4ha_lakes_query) if row[0]}
    gte_10ha_lakes_set = {row[0] for row in arcpy.da.SearchCursor(
        network.waterbody, 'Permanent_Identifier', gte_10ha_lakes_query) if row[0]}

    # area dict
    area_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(network.waterbody, ['Permanent_Identifier', 'AreaSqKm'])}
    # set all the gte 1ha lakes as the seeds
    network.set_start_ids(gte_1ha_lakes_list)

    # create the results of their traces, the traces include all the waterbody-based permids
    results0 = network.trace_up_from_waterbody_starts()

    # drop lakes from their own traces and convert results to set
    results = {k:set(v).difference({k}) for k, v in results0.items()}

    # count how many are in each
    results_1_4_10 = {k:[v.intersection(gte_1ha_lakes_set),
                      v.intersection(gte_4ha_lakes_set),
                      v.intersection(gte_10ha_lakes_set)] for k, v in results.items()}

    # create the output table
    out = arcpy.CreateTable_management(os.path.dirname(output_table), os.path.basename(output_table))
    arcpy.AddField_management(out, 'Permanent_Identifier', 'TEXT', field_length=40)
    arcpy.AddField_management(out, 'lake_lakes1ha_upstream_n', 'LONG')
    arcpy.AddField_management(out, 'lake_lakes1ha_upstream_ha', 'DOUBLE')
    arcpy.AddField_management(out, 'lake_lakes4ha_upstream_n', 'LONG')
    arcpy.AddField_management(out, 'lake_lakes4ha_upstream_ha', 'DOUBLE')
    arcpy.AddField_management(out, 'lake_lakes10ha_upstream_n', 'LONG')
    arcpy.AddField_management(out, 'lake_lakes10ha_upstream_ha', 'DOUBLE')

    cursor_fields = ['Permanent_Identifier',
                     'lake_lakes1ha_upstream_n',
                     'lake_lakes1ha_upstream_ha',
                     'lake_lakes4ha_upstream_n',
                     'lake_lakes4ha_upstream_ha',
                     'lake_lakes10ha_upstream_n',
                     'lake_lakes10ha_upstream_ha']


    # populate the output table
    out_rows = arcpy.da.InsertCursor(out, cursor_fields)

    for wb_id in results: # for all 1ha lakes
        lakes1ha, lakes4ha, lakes10ha = results_1_4_10[wb_id] # each variable is a list
        if wb_id == '{282DD3F2-8B4B-411B-9E2B-0CBB3AECF9EB}':
            print lakes4ha
            print lakes10ha
        lakes1ha_n = len(lakes1ha)
        lakes1ha_ha = sum([100*area_dict[id] for id in lakes1ha])
        lakes4ha_n = len(lakes4ha)
        lakes4ha_ha = sum([100*area_dict[id] for id in lakes4ha])
        lakes10ha_n = len(lakes10ha)
        lakes10ha_ha = sum([100*area_dict[id] for id in lakes10ha])
        new_row = (wb_id, lakes1ha_n, lakes1ha_ha, lakes4ha_n, lakes4ha_ha, lakes10ha_n, lakes10ha_ha)
        out_rows.insertRow(new_row)

    if unique_id == 'lagoslakeid':
        arcpy.AddField_management(out, 'lagoslakeid', 'LONG')
        lagos_dict = {r[0]:r[1] for r in
                      arcpy.da.SearchCursor(network.waterbody, ['Permanent_Identifer', 'lagoslakeid'])}
        with arcpy.da.UpdateCursor(out, ['Permanent_Identifier', 'lagoslakeid']) as u_cursor:
            for row in u_cursor:
                new_row = [row[0], lagos_dict[row[0]]]
                u_cursor.updateRow(new_row)
        arcpy.DeleteField_management(out, 'Permanent_Identifier')

    return out