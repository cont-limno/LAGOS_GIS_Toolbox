import os
import re
from arcpy import management as DM
from arcpy import analysis as AN
import arcpy
import lagosGIS
from datetime import datetime
from collections import defaultdict

def assign_catchments_to_lakes(nhdplus_gdb, output_fc):
    # paths
    nhd_cat = os.path.join(nhdplus_gdb, 'NHDPlusCatchment')
    nhd_flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
    nhd_wb = os.path.join(nhdplus_gdb, 'NHDWaterbody')

    # copy to output and prep
    nhd_cat_copy = DM.CopyFeatures(nhd_cat, output_fc)
    DM.AddField(nhd_cat_copy, 'Lake_PermID', field_type = 'TEXT', field_length = 40)
    DM.AddField(nhd_cat_copy, 'Flowline_PermID', field_type = 'TEXT', field_length = 40)

    # build dictionaries for the joins
    nhd_flowline_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
                                                                   ['NHDPlusID', 'Permanent_Identifier'])}
    nhd_wbarea_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
                                                                   ['NHDPlusID', 'WBArea_Permanent_Identifier'])}
    nhd_wb_dict = {r[0]:r[1] for r in arcpy.da.SearchCursor(nhd_wb, ['NHDPlusID', 'Permanent_Identifier'])}
    valid_wb_ids = set(nhd_wb_dict.values())
    # some WBArea_... values come from NHDArea polygons, not NHDWaterbody. Filter dictionary for valid only.
    flowline_wb_dict = {nhdplusid:nhd_wbarea_dict[nhdplusid] for nhdplusid, wb_permid in nhd_wbarea_dict.items() if wb_permid in valid_wb_ids}

    with arcpy.da.UpdateCursor(nhd_cat_copy, ['NHDPlusID', 'Lake_PermID', 'Flowline_PermID']) as nhd_cat_copy_cursor:

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
            new_row = (nhdplusid, lake_permid, nhd_flowline_dict[nhdplusid])
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

def aggregate_watersheds(watersheds_fc, nhdplus_gdb, eligible_lakes_fc, output_fc,
                         mode = ['interlake', 'network', 'self'], watersheds_permid_field = 'Lake_Permanent_Identifier'):
    """Creates a feature class with all the aggregated upstream watersheds for all
    eligible lakes in this subregion."""
    print(str(datetime.now())) #TODO: Remove
    arcpy.env.workspace = 'in_memory'
    # names
    huc4_code = re.search('\d{4}', os.path.basename(nhdplus_gdb)).group()
    # for some reason, you actually need to specify the feature dataset here unlike usually
    hydro_net_junctions = os.path.join(nhdplus_gdb, 'Hydrography', 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhdplus_gdb, 'Hydrography', 'HYDRO_NET')

    # get this hu4
    wbd_hu4 = os.path.join(nhdplus_gdb, "WBDHU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause4 = """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhdplus_gdb, field_name), huc4_code)
    hu4 = arcpy.Select_analysis(wbd_hu4, "hu4", whereClause4)

    # make layers for upcoming spatial selections
    # and fcs in memory
    junctions = DM.MakeFeatureLayer(hydro_net_junctions, "junctions")
    watersheds = DM.MakeFeatureLayer(watersheds_fc, 'watersheds')
    eligible_lakes_copy = lagosGIS.select_fields(eligible_lakes_fc, 'in_memory/eligible_lakes_copy',
                                                 ['Permanent_Identifier', 'AreaSqKm'])

    # intersect eligible_lakes and catchments for this NHD gdb (eligible_lakes can have much larger extent)
    # any lake id that doesn't intersect/inner join will be DROPPED and will not get a watershed traced
    cat_permids = set([row[0] for row in arcpy.da.SearchCursor(watersheds_fc, watersheds_permid_field)])
    with arcpy.da.UpdateCursor(eligible_lakes_copy, ['Permanent_Identifier']) as u_cursor:
        for row in u_cursor:
            if row[0] not in cat_permids:
                u_cursor.deleteRow()

    # ten ha lakes and junctions
    if mode == 'interlake':
        tenha_where_clause = """"AreaSqKm" >= .1""" # compatible with both LAGOS layer or original NHD
        arcpy.Select_analysis(eligible_lakes_copy, 'tenha_lakes', tenha_where_clause)
        DM.MakeFeatureLayer('tenha_lakes', 'tenha_lakes_lyr')
        DM.SelectLayerByLocation('junctions', 'INTERSECT', 'tenha_lakes', search_distance="1 Meters")
        DM.CopyFeatures('junctions', 'tenha_junctions')
        DM.MakeFeatureLayer('tenha_junctions', 'tenha_junctions_lyr')

    # classify lakes as having junctions or not, so the loop can skip non-network ones quickly
    DM.AddField(eligible_lakes_copy, 'Has_Junctions', 'TEXT', field_length = 1)
    lakes_layer = DM.MakeFeatureLayer(eligible_lakes_copy, 'lakes_layer')
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
        this_watershed = DM.Dissolve("watersheds", "this_watershed") # watersheds has selection on
        DM.AddField(this_watershed, watersheds_permid_field, 'TEXT', field_length=255)
        DM.CalculateField(this_watershed, watersheds_permid_field, """'{}'""".format(id), "PYTHON")
        traced_watershed = arcpy.Erase_analysis(this_watershed, 'this_lake',
                             'lakeless_watershed')
        for item in ['this_lake', 'this_watershed', 'this_lake_jxns', 'upstream']:
            try:
                DM.Delete(item)
            except:
                continue

        return traced_watershed

    print(str(datetime.now())) #TODO: Remove
    # for each lake, calculate its interlake watershed in the upcoming block
    prog_count = int(DM.GetCount(eligible_lakes_copy).getOutput(0))
    counter = 0
    with arcpy.da.SearchCursor(eligible_lakes_copy, ["Permanent_Identifier", "Has_Junctions"]) as cursor:
        for row in cursor:
            counter += 1
            print(counter)# TODO: Remove

            if counter % 100 == 0:
                print("{0} out of {1} lakes completed.".format(counter, prog_count))

            id, has_junctions = row
            print(id) # TODO: Remove
            print(str(datetime.now()))  # TODO: Remove
            lakeless_watershed = trace_a_network(id, has_junctions)

            if not arcpy.Exists("merged_fc"):
                merged_fc = DM.CopyFeatures(lakeless_watershed, 'merged_fc')
                # to avoid append mismatch due to permanent_identifier
                DM.AlterField(merged_fc, watersheds_permid_field, field_length = 255)
            else:
                DM.Append(lakeless_watershed, merged_fc, 'NO_TEST')
            DM.Delete(lakeless_watershed)

    output_hole_remove = DM.EliminatePolygonPart(merged_fc, "output_hole_remove", "AREA", "3.9 Hectares", "0",
                                          "CONTAINED_ONLY")
    output_fc = arcpy.Clip_analysis(output_hole_remove, hu4, output_fc)
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


class NHDPlusNetwork:
    def __init__(self, nhdplus_gdb):
        self.gdb = nhdplus_gdb
        self.waterbody = os.path.join(nhdplus_gdb, 'NHDWaterbody')
        self.flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
        self.flow = os.path.join(nhdplus_gdb, 'NHDPlusFlow')
        self.waterbody_start_ids = []
        self.flowline_start_ids = []
        self.flowline_stop_ids = []
        self.waterbody_stop_ids = []
        self.upstream = defaultdict(list)
        self.flowline_waterbody = defaultdict(list)
        self.waterbody_flowline = defaultdict(list)

    def prepare_upstream(self):
        """Read the file GDB flow table and collapse into a flow dictionary."""
        with arcpy.da.SearchCursor(self.flow, ['FromPermID', 'ToPermID']) as cursor:
            for row in cursor:
                from_id, to_id = row
                if from_id == '0':
                    self.upstream[to_id] = []
                else:
                    self.upstream[to_id].append(from_id)

    def map_flowlines_to_waterbodies(self):
        with arcpy.da.SearchCursor(self.flowline, ['Permanent_Identifier', 'WBArea_Permanent_Identifier']) as cursor:
            for row in cursor:
                flowline_id, waterbody_id = row
                if waterbody_id:
                    self.flowline_waterbody[flowline_id].append(waterbody_id)

    def map_waterbodies_to_flowlines(self):
        with arcpy.da.SearchCursor(self.flowline, ['Permanent_Identifier', 'WBArea_Permanent_Identifier']) as cursor:
            for row in cursor:
                flowline_id, waterbody_id = row
                if waterbody_id:
                    self.waterbody_flowline[waterbody_id].append(flowline_id)
        return self.waterbody_flowline

    def set_stop_ids(self, waterbody_stop_ids):
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        self.waterbody_stop_ids = waterbody_stop_ids
        flowline_ids_unflat = [self.waterbody_flowline[lake_id] for lake_id in waterbody_stop_ids]
        # flatten before returning
        self.flowline_stop_ids = [id for id_list in flowline_ids_unflat for id in id_list]

    def set_start_ids(self, waterbody_start_ids):
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        self.waterbody_start_ids = waterbody_start_ids
        flowline_ids_unflat = [self.waterbody_flowline[lake_id] for lake_id in waterbody_start_ids]
        # flatten before returning
        self.flowline_start_ids = [id for id_list in flowline_ids_unflat for id in id_list]

    def activate_10ha_lake_stops(self):
        self.waterbody_stop_ids = []
        lagos_fcode_list = lagosGIS.LAGOS_FCODE_LIST
        with arcpy.da.SearchCursor(self.waterbody, ['Permanent_Identifier', 'AreaSqKm', 'FCode']) as cursor:
            for row in cursor:
                id, area, fcode = row
                if area >= 0.1 and fcode in lagos_fcode_list:
                    self.waterbody_stop_ids.append(id)
        # and set the flowlines too
        self.set_stop_ids(self.waterbody_stop_ids)

    def trace_up_from_a_flowline(self, flowline_start_id):
        if not self.upstream:
            self.prepare_upstream()
        stop_ids_set = set(self.flowline_stop_ids)

        # get the next IDs up from the start
        from_ids = self.upstream[flowline_start_id]
        all_from_ids = from_ids[:]
        all_from_ids.append(flowline_start_id) # include start point in trace

        # while there is still network left, iteratively trace up and add on
        while from_ids:
            next_up = [self.upstream[id] for id in from_ids]

            # flatten results
            next_up_flat = list(set([id for id_list in next_up for id in id_list]))
            if stop_ids_set:
                next_up_flat = [id for id in next_up_flat if id not in stop_ids_set]

            # seed the new start point
            from_ids = next_up_flat
            all_from_ids.extend(from_ids)
        return all_from_ids

    def trace_up_from_a_waterbody(self, waterbody_start_id):
        if not self.upstream:
            self.prepare_upstream()
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        flowline_start_ids = set(self.waterbody_flowline[waterbody_start_id]) # one or more
        # remove waterbody's own flowlines from stop ids--don't want them to stop themselves
        self.flowline_stop_ids = [id for id in self.flowline_stop_ids if id not in flowline_start_ids]

        # first identify only the lowest start ids
        next_up = [self.upstream[id] for id in flowline_start_ids]
        next_up_flat = {id for id_list in next_up for id in id_list}
        lowest_flowline_start_ids = flowline_start_ids.difference(next_up_flat) # lakes may have multiple outlets
        print lowest_flowline_start_ids

        # then trace up for all
        unflat_trace_all = [self.trace_up_from_a_flowline(id) for id in lowest_flowline_start_ids]
        all_from_ids = list({id for id_list in unflat_trace_all for id in id_list})

        # reset flowline_stop_ids
        self.flowline_stop_ids = self.flowline_stop_ids.extend(flowline_start_ids)
        return all_from_ids

    def trace_up_from_waterbody_starts(self):
        if self.waterbody_start_ids:
            results = {id:self.trace_up_from_a_waterbody(id) for id in self.waterbody_start_ids}
            return results
        else:
            raise Exception("Populate start IDs with set_start_ids before calling trace_up_from_starts().")






# def calc_upstream_dict(flow_table):
#     """Read the file GDB flow table and collapse into a flow dictionary."""
#     upstream = defaultdict(list)
#     with arcpy.da.SearchCursor(flow_table, ['FromPermID', 'ToPermID']) as cursor:
#         for row in cursor:
#             from_id, to_id = row
#             if from_id == '0':
#                 upstream[to_id] = []
#             else:
#                 upstream[to_id].append(from_id)
#     return upstream
#
#
# def trace_up_from_flowline(upstream_dict, flowline_to_id, filter_id_list):
#     """Trace upstream from a Permanent_Identifier, returning only the upstream IDs in the filter list (such as a list
#     of eligible lake IDs) if one is provided."""
#     filter_id_set = set(filter_id_list)
#     from_ids = upstream_dict[flowline_to_id]
#     new_from_ids = from_ids[:]
#     while from_ids:
#         next_up = [upstream_dict[id] for id in from_ids]
#         from_ids = list(set([id for id_list in next_up for id in id_list]))
#         new_from_ids.extend(from_ids)
#     if filter_id_set:
#         new_from_ids = [id for id in new_from_ids if id in filter_id_set]
#     return new_from_ids
