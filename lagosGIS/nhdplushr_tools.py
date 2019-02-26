import os
import re
from arcpy import management as DM
from arcpy import analysis as AN
import arcpy
import csiutils as cu # TODO: eliminate

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
    catchments_assigned = assign_catchments_to_lakes(nhdplus_gdb, 'catchments_assigned')

    # set NHDPlusID to null if lake ID is populated, so that we can dissolve all lake catchments into one
    # but keep the distinct flowline segment catchments also
    with arcpy.da.UpdateCursor(catchments_assigned, ['NHDPlusID', 'Lake_Permanent_Identifier']) as u_cursor:
        for row in u_cursor:
            if row[1]:
                row[0] = None
            u_cursor.updateRow(row)

    output_fc = DM.Dissolve(catchments_assigned, output_catchments_fc, 'Lake_Permanent_Identifier')
    DM.AddIndex(output_fc, 'Lake_Permanent_Identifier', 'lake_id_idx')
    arcpy.Delete_management(catchments_assigned)
    return output_fc

def aggregate_watersheds(nhdplus_gdb, eligible_lakes_fc, output_fc, mode = ['interlake', 'network', 'self']):
    """Creates a feature class with all the aggregated upstream watersheds for all
    eligible lakes in this subregion."""

    arcpy.env.workspace = 'in_memory'

    # names
    huc4_code = re.search('\d{4}', os.path.basename(nhdplus_gdb)).group()

    hydro_net_junctions = os.path.join(nhdplus_gdb, 'Hydrography', 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhdplus_gdb, 'Hydrography', 'HYDRO_NET')
    watersheds_fc = os.path.join(nhdplus_gdb, 'Local_Catchments_Original_Methods') # TODO: Change to NHDCatchment
    watersheds_permid_field = 'Permanent_Identifier'

    # get this hu4
    wbd_hu4 = os.path.join(nhdplus_gdb, "WBD_HU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause4 = """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhdplus_gdb, field_name), huc4_code)
    arcpy.Select_analysis(wbd_hu4, "hu4", whereClause4)

    # add unique junction IDs to cut down on spatial selections
    # make layers for upcoming spatial selections
    # junctions_copy = DM.CopyFeatures(hydro_net_junctions, 'junctions_copy')
    # DM.AddField(junctions_copy, 'junction_id', 'SHORT')
    # junction_id = 1
    # with arcpy.da.UpdateCursor(junctions_copy, ['junction_id']) as u_cursor:
    #     for row in u_cursor:
    #         junction_id +=1
    #         new_row = (junction_id,)
    #         u_cursor.updateRow(new_row)
    # DM.AddIndex(junctions_copy, 'junction_id', 'junction_id_idx') # worth it, queried once per lake later

    junctions = DM.MakeFeatureLayer(hydro_net_junctions, "junctions") # TODO: Change back to junctions_copy
    watersheds = DM.MakeFeatureLayer(watersheds_fc, 'watersheds')

    # ten ha lakes and junctions
    if mode == 'interlake':
        tenha_where_clause = """"AreaSqKm" >= .1"""
        tenha_lakes = AN.Select(eligible_lakes_fc, 'tenha_lakes', tenha_where_clause)
         # DM.AddIndex(tenha_lakes, 'Permanent_Identifier', 'permid_idx') # worth it, queried once per lake later

        DM.SelectLayerByLocation(junctions, 'INTERSECT', tenha_lakes, search_distance="1 Meters")
        tenha_junctions = DM.CopyFeatures(junctions, 'tenha_junctions')
        tenha_junctions_lyr = arcpy.MakeFeatureLayer_management('tenha_junctions', 'tenha_junctions_lyr') # TODO:

    # for each lake, calculate its interlake watershed in the upcoming block
    prog_count = int(arcpy.GetCount_management(eligible_lakes_fc).getOutput(0))
    counter = 0

    # skip lakes that have no junctions whatsoever
    eligible_lakes_copy = DM.CopyFeatures(eligible_lakes_fc, 'eligible_lakes_copy')
    DM.AddField(eligible_lakes_copy, 'Has_Junctions', 'TEXT', field_length = 1)
    lakes_layer = DM.MakeFeatureLayer(eligible_lakes_copy)
    DM.SelectLayerByLocation(lakes_layer, 'INTERSECT', hydro_net_junctions, search_distance = '1 Meters')
    DM.CalculateField(lakes_layer, 'Has_Junctions', "'Y'", 'PYTHON')

    with arcpy.da.SearchCursor(eligible_lakes_copy, ["Permanent_Identifier", "Has_Junctions"]) as cursor:
        for row in cursor:
            counter += 1
            if counter % 50 == 0:
                print("{0} out of {1} lakes completed.".format(counter, prog_count))

            id, has_junctions = row
            where_clause = """"{0}" = '{1}'""".format("Permanent_Identifier", id)
            this_lake = DM.MakeFeatureLayer(eligible_lakes_copy, "this_lake",
                                              where_clause)
            if not has_junctions:
                where_clause2 = """"{0}" = '{1}'""".format(watersheds_permid_field, id)
                DM.SelectLayerByAttribute(watersheds, where_clause = where_clause2) # sheds = own orig. shed
            else:
                DM.SelectLayerByLocation(junctions, "INTERSECT", this_lake, search_distance = "1 Meters") # new selection
                this_lake_jxns = DM.CopyFeatures(junctions, 'this_lake_jxns')
                if mode == 'interlake':
                    arcpy.SelectLayerByLocation_management(tenha_junctions_lyr, 'ARE_IDENTICAL_TO',
                                                           'this_lake_jxns', invert_spatial_relationship = 'INVERT')
                    other_tenha_junctions = arcpy.CopyFeatures_management(tenha_junctions_lyr, 'other_tenha_junctions')


                    # junction_ids = tuple([row[0] for row in arcpy.da.SearchCursor(this_lake_jxns, 'junction_id')])
                    # other_tenha_junctions = AN.Select(tenha_junctions, 'other_tenha_junctions',
                    #                                   "junction_id NOT IN {}".format(junction_ids))
                    not_this_lake_query = """"{0}" <> '{1}'""".format("Permanent_Identifier", id)
                    other_tenha_lakes = DM.MakeFeatureLayer(tenha_lakes, 'other_tenha_lakes', not_this_lake_query)
                    arcpy.TraceGeometricNetwork_management(hydro_net, "upstream",
                                                           'this_lake_jxns', "TRACE_UPSTREAM",
                                                           in_barriers='other_tenha_junctions')
                elif mode == 'cumulative':
                    arcpy.TraceGeometricNetwork_management(hydro_net, "upstream",
                                                           this_lake_jxns, "TRACE_UPSTREAM")

                # FOR BOTH ACCUMULATTION TYPES, SELECT OWN/UPSTREAM WATERSHEDS
                arcpy.SelectLayerByLocation_management(watersheds, "CONTAINS",
                                                       "upstream/NHDFlowline") # sheds select 1 -- contains network
                # sheds select 2 -- adds to 1
                DM.SelectLayerByLocation(watersheds, 'CROSSED_BY_THE_OUTLINE_OF',
                                                       'upstream/NHDFLowline', selection_type="ADD_TO_SELECTION")
                # # can this section ever actually happen now? should at least contain own shed always.
                # # if script fails, uncomment this part
                # watersheds_count = int(arcpy.GetCount_management(watersheds).getOutput(0))
                # if watersheds_count == 0:
                #     DM.SelectLayerByLocation(watersheds, 'CONTAINS', this_lake) # sheds select 3: replace sel2 if empty

            # Sometimes when the trace stops at 10-ha lake, selects that shed(s).
            # Remove sheds intersecting OTHER 10-ha lakes
                if mode == 'interlake':
                    DM.SelectLayerByLocation(watersheds, "CONTAINS", other_tenha_lakes,
                                    selection_type="REMOVE_FROM_SELECTION") # watersheds selection 5 (removes from 4)

            # FOR ALL LAKES: dissolve, erase (each of these tasks must be done one-by-one for each lake)
            this_watershed = DM.Dissolve(watersheds, "this_watershed")
            DM.AddField(this_watershed, 'Permanent_Identifier', 'TEXT', field_length=255)
            arcpy.CalculateField_management(this_watershed, "Permanent_Identifier", """'{}'""".format(id), "PYTHON")
            lakeless_watershed = arcpy.Erase_analysis(this_watershed, this_lake,
                                 'lakeless_watershed')

            if not arcpy.Exists("merged_fc"):
                merged_fc = DM.CopyFeatures(lakeless_watershed, "merged_fc")
                # to avoid append mismatch due to permanent_identifier
                DM.AlterField(merged_fc, 'Permanent_Identifier', field_length = 255)
            else:
                arcpy.Append_management('lakeless_watershed', merged_fc, 'NO_TEST')
            for item in ['this_lake', 'this_watershed', 'this_lake_jxns', 'other_tenha_junctions', 'other_tenha_lakes', 'upstream', 'lakeless_watershed']:
                try:
                    arcpy.Delete_management(item)
                except:
                    continue

    output_hole_remove = DM.EliminatePolygonPart(merged_fc, "output_hole_remove", "AREA", "3.9 Hectares", "0",
                                          "CONTAINED_ONLY")
    output_fc = arcpy.Clip_analysis(output_hole_remove, "hu4", output_fc)
    arcpy.Delete_management('merged_fc')
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



