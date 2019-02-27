import os
import re
from arcpy import management as DM
from arcpy import analysis as AN
import arcpy

def assign_catchments_to_lakes(nhdplus_gdb, output_fc):
    # paths
    nhd_cat = os.path.join(nhdplus_gdb, 'NHDPlusCatchment')
    nhd_flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
    nhd_wb = os.path.join(nhdplus_gdb, 'NHDWaterbody')

    # copy to output and prep
    nhd_cat_copy = DM.CopyFeatures(nhd_cat, output_fc)
    DM.AddField(nhd_cat_copy, 'Lake_Permanent_Identifier', field_type = 'TEXT', field_length = 40)

    # build dictionaries for the joins
    nhd_flowline_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
                                                                   ['NHDPlusID', 'WBArea_Permanent_Identifier'])}
    nhd_wb_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(nhd_wb, ['NHDPlusID', 'Permanent_Identifier'])}
    valid_wb_ids = set(nhd_wb_dict.values())
    # some WBArea_... values come from NHDArea polygons, not NHDWaterbody. Filter dictionary for valid only.
    flowline_wb_dict = {nhdplusid:nhd_flowline_dict[nhdplusid] for nhdplusid, wb_permid in nhd_flowline_dict.items() if wb_permid in valid_wb_ids}

    with arcpy.da.UpdateCursor(nhd_cat_copy, ['NHDPlusID', 'Lake_Permanent_Identifier']) as nhd_cat_copy_cursor:

        # use UpdateCursor to "join" to get waterbody ids
        for u_row in nhd_cat_copy_cursor:
            nhdplusid = u_row[0]
            lake_permid_flowline = None
            lake_permid_sink = None

            # like SELECT WBArea_Permanent_Identifier FROM nhd_cat LEFT JOIN nhd_flowline
            if nhdplusid in flowline_wb_dict:
                lake_permid_flowline = flowline_wb_dict[nhdplusid]

            # join to sinks to get sink to lake mapping
            # like SELECT Permanent_Identifier FROM nhd_cat LEFT JOIN nhd_wb
            if nhdplusid in nhd_wb_dict:
                lake_permid_sink = nhd_wb_dict[nhdplusid]

            # concatenate & calculate update
            if lake_permid_flowline:
                lake_permid = lake_permid_flowline
            else:
                lake_permid = lake_permid_sink

            # write the update
            new_row = (nhdplusid, lake_permid)
            nhd_cat_copy_cursor.updateRow(new_row)

    return nhd_cat_copy


def merge_lake_catchments(nhdplus_gdb, output_catchments_fc):
    arcpy.env.workspace = 'in_memory'
    # nhdwaterbody = os.path.join(nhdplus_gdb, 'NHDWaterbody')
    catchments_assigned = assign_catchments_to_lakes(nhdplus_gdb, 'catchments_assigned')

    # dissolve the lake catchments and separate out the stream catchments layer
    stream_cats = AN.Select(catchments_assigned, 'stream_cats', 'Lake_Permanent_Identifier IS NULL')
    lake_cats = AN.Select(catchments_assigned, 'lake_cats', 'Lake_Permanent_Identifier IS NOT NULL')
    dissolved_lake_cats = DM.Dissolve(lake_cats, 'dissolved_lake_cats', ['Lake_Permanent_Identifier'])
    DM.AddField(dissolved_lake_cats, 'NHDPlusID', 'DOUBLE') # leave as all NULL on purpose

    # # update each lake watershed shape so that it includes the entire lake/cannot extend beyond the lake.
    # wb_shapes_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhdwaterbody, ['Permanent_Identifier', 'SHAPE@'])}
    # with arcpy.da.UpdateCursor(dissolved_lake_cats, ['Lake_Permanent_Identifier', 'SHAPE@']) as u_cursor:
    #     for row in u_cursor:
    #         id, shape = row
    #         wb_shape = wb_shapes_dict[id]
    #         new_shape = shape.union(wb_shape)
    #         u_cursor.updateRow((id, new_shape))
    #
    # # erase all lake catchments from stream catchments so there are no overlaps
    # output_fc = AN.Update(stream_cats, dissolved_lake_cats, output_catchments_fc)
    output_fc = DM.Merge([stream_cats, dissolved_lake_cats], output_catchments_fc)
    DM.AddIndex(output_fc, 'Lake_Permanent_Identifier', 'lake_id_idx')
    DM.Delete('in_memory')
    return output_fc

def aggregate_watersheds(nhdplus_gdb, eligible_lakes_fc, output_fc, mode = ['interlake', 'network', 'self']):
    """Creates a feature class with all the aggregated upstream watersheds for all
    eligible lakes in this subregion."""

    arcpy.env.workspace = 'in_memory'

    # names
    huc4_code = re.search('\d{4}', os.path.basename(nhdplus_gdb)).group()
    # for some reason, you actually need to specify the feature dataset here unlike usually
    hydro_net_junctions = os.path.join(nhdplus_gdb, 'Hydrography', 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhdplus_gdb, 'Hydrography', 'HYDRO_NET')
    watersheds_fc = os.path.join(nhdplus_gdb, 'Local_Catchments_Original_Methods') # TODO: Change to NHDCatchment
    watersheds_permid_field = 'Permanent_Identifier'

    # get this hu4
    wbd_hu4 = os.path.join(nhdplus_gdb, "WBD_HU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause4 = """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhdplus_gdb, field_name), huc4_code)
    hu4 = arcpy.Select_analysis(wbd_hu4, "hu4", whereClause4)

    # make layers for upcoming spatial selections
    # and fcs in memory
    watersheds_fc = DM.CopyFeatures(watersheds_fc, 'watersheds_fc')
    eligible_lakes_fc = DM.CopyFeatures(eligible_lakes_fc, 'eligible_lakes_fc')
    junctions = DM.MakeFeatureLayer(hydro_net_junctions, "junctions")
    watersheds = DM.MakeFeatureLayer(watersheds_fc, 'watersheds')

    # ten ha lakes and junctions
    if mode == 'interlake':
        tenha_where_clause = """"AreaSqKm" >= .1"""
        arcpy.Select_analysis(eligible_lakes_fc, 'tenha_lakes', tenha_where_clause)
        DM.MakeFeatureLayer('tenha_lakes', 'tenha_lakes_lyr')
        DM.SelectLayerByLocation('junctions', 'INTERSECT', 'tenha_lakes', search_distance="1 Meters")
        DM.CopyFeatures('junctions', 'tenha_junctions')
        DM.MakeFeatureLayer('tenha_junctions', 'tenha_junctions_lyr')
    # for each lake, calculate its interlake watershed in the upcoming block
    prog_count = int(DM.GetCount(eligible_lakes_fc).getOutput(0))
    counter = 0

    # classify lakes as having junctions or not, so the loop can skip non-network ones quickly
    eligible_lakes_copy = DM.CopyFeatures(eligible_lakes_fc, 'eligible_lakes_copy')
    DM.AddField(eligible_lakes_copy, 'Has_Junctions', 'TEXT', field_length = 1)
    lakes_layer = DM.MakeFeatureLayer(eligible_lakes_copy)
    DM.SelectLayerByLocation(lakes_layer, 'INTERSECT', hydro_net_junctions, search_distance = '1 Meters')
    DM.CalculateField(lakes_layer, 'Has_Junctions', "'Y'", 'PYTHON')

    # define the network trace function (inside the parent function because so many layers referenced)
    def trace_a_network(id, has_junctions = True):
        where_clause = """"{0}" = '{1}'""".format("Permanent_Identifier", id)
        this_lake = DM.MakeFeatureLayer(eligible_lakes_copy, "this_lake",
                                        where_clause)
        if not has_junctions:
            where_clause2 = """"{0}" = '{1}'""".format(watersheds_permid_field, id)
            DM.SelectLayerByAttribute(watersheds, where_clause=where_clause2)  # sheds = own orig. shed
        else:
            DM.SelectLayerByLocation(junctions, "INTERSECT", this_lake, search_distance="1 Meters")  # new selection
            this_lake_jxns = DM.CopyFeatures(junctions, 'this_lake_jxns')
            if mode == 'interlake':
                DM.SelectLayerByLocation('tenha_junctions_lyr', 'ARE_IDENTICAL_TO',
                                         this_lake_jxns, invert_spatial_relationship='INVERT')
                DM.CopyFeatures('tenha_junctions_lyr', 'other_tenha_junctions')
                DM.SelectLayerByLocation('tenha_lakes_lyr', 'INTERSECT', 'other_tenha_junctions',
                                         search_distance='1 Meters')

                DM.TraceGeometricNetwork(hydro_net, "upstream",
                                         'this_lake_jxns', "TRACE_UPSTREAM",
                                         in_barriers='other_tenha_junctions')
            elif mode == 'cumulative':
                DM.TraceGeometricNetwork(hydro_net, "upstream",
                                         'this_lake_jxns', "TRACE_UPSTREAM")
            DM.SelectLayerByLocation("watersheds", "CONTAINS",
                                     "upstream/NHDFlowline")
            DM.SelectLayerByLocation("watersheds", 'CROSSED_BY_THE_OUTLINE_OF',
                                     'upstream/NHDFLowline', selection_type="ADD_TO_SELECTION")

            # Sometimes when the trace stops at 10-ha lake, selects that shed(s).
            # Remove sheds intersecting OTHER 10-ha lakes
            if mode == 'interlake':
                DM.SelectLayerByLocation("watersheds", "CONTAINS", "tenha_lakes_lyr",
                                         selection_type="REMOVE_FROM_SELECTION")

            # safeguard against 10-hectare lake removal step above removing aggressively in case of mismatch
            # and any other event that could have resulted in all portions of the watershed being empty
            watersheds_count = int(DM.GetCount("watersheds").getOutput(0))
            if watersheds_count == 0:
                DM.SelectLayerByLocation('watersheds', 'CONTAINS', 'this_lake')

        # FOR ALL LAKES: dissolve, erase (each of these tasks must be done one-by-one for each lake)
        this_watershed = DM.Dissolve("watersheds", "this_watershed")
        DM.AddField(this_watershed, 'Permanent_Identifier', 'TEXT', field_length=255)
        DM.CalculateField(this_watershed, "Permanent_Identifier", """'{}'""".format(id), "PYTHON")
        traced_watershed = arcpy.Erase_analysis(this_watershed, 'this_lake',
                             'lakeless_watershed')
        for item in ['this_lake', 'this_watershed', 'this_lake_jxns', 'upstream']:
            try:
                DM.Delete(item)
            except:
                continue

        return traced_watershed

    with arcpy.da.SearchCursor(eligible_lakes_copy, ["Permanent_Identifier", "Has_Junctions"]) as cursor:
        for row in cursor:
            counter += 1
            if counter % 50 == 0:
                print("{0} out of {1} lakes completed.".format(counter, prog_count))
            id, has_junctions = row
            lakeless_watershed = trace_a_network(id, has_junctions)

            if not arcpy.Exists("merged_fc"):
                merged_fc = DM.CopyFeatures(lakeless_watershed, 'merged_fc')
                # to avoid append mismatch due to permanent_identifier
                DM.AlterField(merged_fc, 'Permanent_Identifier', field_length = 255)
            else:
                DM.Append(lakeless_watershed, merged_fc, 'NO_TEST')
            DM.Delete(lakeless_watershed)

    output_hole_remove = DM.EliminatePolygonPart(merged_fc, "output_hole_remove", "AREA", "3.9 Hectares", "0",
                                          "CONTAINED_ONLY")
    output_fc = arcpy.Clip_analysis(output_hole_remove, "hu4", output_fc)
    DM.Delete(merged_fc)
    arcpy.ResetEnvironments()
    return output_fc


def calculate_waterbody_strahler(nhdplus_gdb, output_table):
    nhd_wb = os.path.join(nhdplus_gdb, 'NHDWaterbody')
    nhd_flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
    nhd_vaa = os.path.join(nhdplus_gdb, 'NHDPlusFlowlineVAA')

    # build dictionaries for the joins
    nhd_wb_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_wb, ['Permanent_Identifier', 'NHDPlusID'])}
    # filter upcoming dictionary to only include artificial flowlines (but with both waterbody and NHDArea ids)
    nhd_flowline_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
                                                ['NHDPlusID', 'WBArea_Permanent_Identifier']) if r[1]}
    # filter out flowlines we can't get strahler for NOW, so that loop below doesn't have to test
    nhd_vaa_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_vaa, ['NHDPlusID', 'StreamOrde'])
                    if r[0] in nhd_flowline_dict}
    # filter out lines with uninitialized flow as they don't appear in nhd_vaa_dict
    nhd_flowline_dict2 = {key:val for key,val in nhd_flowline_dict.items() if key in nhd_vaa_dict}

    # set up new table
    output_table = DM.CreateTable(os.path.dirname(output_table), os.path.basename(output_table))
    DM.AddField(output_table, 'Lake_Permanent_Identifier', 'TEXT', field_length=40)
    DM.AddField(output_table, 'NHDPlusID', 'DOUBLE')
    DM.AddField(output_table, 'lake_higheststrahler', 'SHORT')
    DM.AddField(output_table, 'lake_loweststrahler', 'SHORT')

    # set up cursor
    out_rows = arcpy.da.InsertCursor(output_table, ['Lake_Permanent_Identifier',
                                                    'NHDPlusID',
                                                    'lake_higheststrahler',
                                                    'lake_loweststrahler'])

    # function to call for each waterbody
    nhd_flowline_dict_items = nhd_flowline_dict2.items()
    def get_matching_strahlers(wb_permid):
        matching_strahlers = [nhd_vaa_dict[flow_plusid] for flow_plusid, linked_wb_permid
                              in nhd_flowline_dict_items if linked_wb_permid == wb_permid]
        return matching_strahlers

    # populate the table with the cursor
    for wb_permid, nhdplusid in nhd_wb_dict.items():
        strahlers = get_matching_strahlers(wb_permid)
        if strahlers:
            new_row = (wb_permid, nhdplusid, max(strahlers), min(strahlers))
        else:
            new_row = (wb_permid, nhdplusid, None, None)
        out_rows.insertRow(new_row)

    del out_rows



