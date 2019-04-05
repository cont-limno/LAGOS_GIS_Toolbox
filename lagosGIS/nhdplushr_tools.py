import os
import re
from collections import defaultdict
from arcpy import management as DM
from arcpy import analysis as AN
import arcpy
import lagosGIS
import csiutils


class NHDNetwork:

    """

    Class for assessing network connectivity within an NHD HR or NHDPlus HR geodatabase.

    :param str nhdplus_gdb: An NHD or NHDPlus HR geodatabase containing the network information.
    :param bool is_plus: Whether the geodatabase is NHDPlus (True) or NHD (False).

    Attributes
    ----------
    :ivar gdb: NHD or NHDPlus geodatabase assigned to the instance
    :ivar str flow: Path for NHDPlusFLow or NHDFlow table
    :ivar str catchmetn: Path for NHDPlusCatchment feature class
    :ivar str sink: Path for NHDPlusSink feature class
    :ivar str waterbody: Path for NHDWaterbody feature class
    :ivar str flowline: Path for NHDFLowline feature class
    :ivar list waterbody_start_ids: List of Permanent_Identifiers for waterbodies set as network tracing start locations
    :ivar dict nhdpid_flowline: Dictionary with key = Flowline NHDPlusID, value = Flowline Permanent_Identifier, created
    from NHDFLowline feature class
    :ivar dict flowline_waterbody: Dictionary with key = Flowline Permanent_Identifier, value = (associated) waterbody
    Permanent_Identifier, created from NHDFlowline feature class
    :ivar dict waterbody_flowline: Dictionary with key = Waterbody Permanent_Identifier, value = list of(associated)
    flowline Permanent_Identifiers, created from NHDFlowline feature class
    :ivar dict waterbody_nhdpid: Dictionary with key = Waterbody Permanent_Identifier, value = Waterbody NHDPlusID,
    created from NHDWaterbody feature class
    :ivar dict nhdpid_waterbody: Dictionary with key = Waterbody NHDPlusID, value = Waterbody Permanent_Identifier,
    created from NHDWaterbody feature class

    """

    def __init__(self, nhd_gdb, is_plus=True):
        self.gdb = nhd_gdb
        self.plus = is_plus

        if self.plus:
            self.from_column = 'FromPermID'
            self.to_column = 'ToPermID'
            self.flow = os.path.join(self.gdb, 'NHDPlusFlow')
        else:
            self.from_column = 'From_Permanent_Identifier'
            self.to_column = 'To_Permanent_Identifier'
            self.flow = os.path.join(self.gdb, 'NHDFlow')
            self.catchment = os.path.join(self.gdb, 'NHDPlusCatchment')
            self.sink = os.path.join(self.gdb, 'NHDPlusSink')

        self.waterbody = os.path.join(self.gdb, 'NHDWaterbody')
        self.flowline = os.path.join(self.gdb, 'NHDFlowline')

        # empty until used
        self.waterbody_start_ids = []
        self.flowline_start_ids = []
        self.flowline_stop_ids = []
        self.waterbody_stop_ids = []
        self.upstream = defaultdict(list)
        self.downstream = defaultdict(list)
        self.nhdpid_flowline = defaultdict(list)
        self.flowline_waterbody = defaultdict(list)
        self.waterbody_flowline = defaultdict(list)
        self.waterbody_nhdpid = defaultdict(list)
        self.nhdpid_waterbody = defaultdict(list)
        self.inlets = []
        self.outlets = []


    def prepare_upstream(self):
        """Read the geodatabase flow table and collapse into a flow dictionary."""
        if not self.upstream:
            with arcpy.da.SearchCursor(self.flow, [self.from_column, self.to_column]) as cursor:
                for row in cursor:
                    from_id, to_id = row
                    if from_id == '0':
                        self.upstream[to_id] = []
                    else:
                        self.upstream[to_id].append(from_id)

    def prepare_downstream(self):
        """Read the geodatabase flow table and collapse into a flow dictionary."""
        if not self.downstream:
            with arcpy.da.SearchCursor(self.flow, [self.from_column, self.to_column]) as cursor:
                for row in cursor:
                    from_id, to_id = row
                    if to_id == '0':
                        self.downstream[from_id] = []
                    else:
                        self.downstream[from_id].append(to_id)

    def map_nhdpid_to_flowlines(self):
        """Construct the nhdpid_flowline identifier mapping dictionary."""
        self.nhdpid_flowline = {r[0]:r[1]
                         for r in arcpy.da.SearchCursor(self.flowline, ['NHDPlusID', 'Permanent_Identifier'])}

    def map_waterbody_to_nhdpids(self):
        """Construct the waterbody_nhdpid and nhdpid_waterbody identifier mapping dictionaries."""
        self.waterbody_nhdpid = {r[0]:r[1]
                         for r in arcpy.da.SearchCursor(self.waterbody, ['Permanent_Identifier', 'NHDPlusID'])}
        self.nhdpid_waterbody = {v:k for k, v in self.waterbody_nhdpid.items()}

    def map_flowlines_to_waterbodies(self):
        """Construct the flowline_waterbody identifier mapping dictionary."""
        self.flowline_waterbody = {r[0]:r[1]
                                   for r in arcpy.da.SearchCursor(self.flowline,
                                                             ['Permanent_Identifier', 'WBArea_Permanent_Identifier'])
                                                             if r[1]}

    def map_waterbodies_to_flowlines(self):
        """Construct the waterbody_flowline identifier mapping dictionary."""
        with arcpy.da.SearchCursor(self.flowline, ['Permanent_Identifier', 'WBArea_Permanent_Identifier']) as cursor:
            for row in cursor:
                flowline_id, waterbody_id = row
                if waterbody_id:
                    self.waterbody_flowline[waterbody_id].append(flowline_id)

    def identify_inlets(self):
        """Identify inlets: flowlines that flow in but have no upstream flowline in this gdb."""
        if not self.downstream:
            self.prepare_downstream()

        from_ids = set(self.downstream.keys()).difference({'0'})
        to_all = {f for to_list in self.downstream.values() for f in to_list}
        upstream_outlets = list(set(from_ids).difference(set(to_all)))
        inlets_unflat = [v for k, v in self.downstream.items() if k in upstream_outlets]
        inlets = [i for i_list in inlets_unflat for i in i_list]
        self.inlets = inlets
        return inlets

    def identify_outlets(self):
        """Identify inlets: flowlines that flow in but have no upstream flowline in this gdb."""
        if not self.upstream:
            self.prepare_upstream()

        to_ids = set(self.upstream.keys()).difference({'0'})
        from_all = {f for from_list in self.upstream.values() for f in from_list}
        downstream_inlets = list(set(to_ids).difference(set(from_all)))
        outlets_unflat = [v for k, v in self.upstream.items() if k in downstream_inlets]
        outlets = [o for o_list in outlets_unflat for o in o_list]
        self.outlets = outlets
        return outlets

    def set_stop_ids(self, waterbody_stop_ids):
        """
        Activate network elements (waterbody and flowline) to be used as barriers for upstream tracing.

        Flow cannot proceed through barriers, therefore the highest points in the traced network will be below the
        barrier elements.

        :param list waterbody_stop_ids: List of waterbody Permanent_Identifiers to act as barriers.

        """
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        self.waterbody_stop_ids = waterbody_stop_ids
        flowline_ids_unflat = [self.waterbody_flowline[lake_id] for lake_id in waterbody_stop_ids]
        # flatten before returning
        self.flowline_stop_ids = [id for id_list in flowline_ids_unflat for id in id_list]

    def set_start_ids(self, waterbody_start_ids):
        """
        Activate network elements (waterbody and flowline) to be used as destinations for flow.

        Tracing proceeds upstream from "start" locations.

        :param list waterbody_start_ids: List of waterbody Permanent_Identifiers to act as trace destinations (or tracing
        start locations).

        """
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        self.waterbody_start_ids = waterbody_start_ids
        flowline_ids_unflat = [self.waterbody_flowline[lake_id] for lake_id in waterbody_start_ids]
        # flatten before returning
        self.flowline_start_ids = [id for id_list in flowline_ids_unflat for id in id_list]

    def activate_10ha_lake_stops(self):
        """Activate flow barriers at all lakes (as defined by LAGOS) greater than 10 hectares in size."""
        self.waterbody_stop_ids = []
        lagos_fcode_list = lagosGIS.LAGOS_FCODE_LIST
        with arcpy.da.SearchCursor(self.waterbody, ['Permanent_Identifier', 'AreaSqKm', 'FCode']) as cursor:
            for row in cursor:
                id, area, fcode = row
                if area >= 0.1 and fcode in lagos_fcode_list:
                    self.waterbody_stop_ids.append(id)
        # and set the flowlines too
        self.set_stop_ids(self.waterbody_stop_ids)

    def deactivate_stops(self):
        """Deactivate all network barriers (flow proceeds unimpeded through entire network)."""
        self.waterbody_stop_ids = []
        self.flowline_stop_ids = []

    def trace_up_from_a_flowline(self, flowline_start_id, include_wb_permids = True):
        """
        Trace a network upstream of the input flowline and return the traced network identifiers in a list.

        Barriers currently activated on the network will be respected by the trace.

        A trace includes its own starting flowline.

        :param str flowline_start_id: Flowline Permanent_Identifier of flow destination (upstream trace start point).
        :param bool include_wb_permids: Whether to include waterbody Permanent_Identifiers in the trace. When False,
        only flowline Permanent_Identifiers will be returned.
        :return: List of Permanent_Identifier values for flowlines and/or waterbodies in the upstream network trace,
        which includes the input flow destination

        """
        if not self.upstream:
            self.prepare_upstream()
        if self.flowline_stop_ids:
            stop_ids_set = set(self.flowline_stop_ids)

        # get the next IDs up from the start
        from_ids = self.upstream[flowline_start_id]
        all_from_ids = from_ids[:]
        all_from_ids.append(flowline_start_id)  # include start point in trace

        # while there is still network left, iteratively trace up and add on
        while from_ids:
            next_up = [self.upstream[id] for id in from_ids]

            # flatten results
            next_up_flat = list(set([id for id_list in next_up for id in id_list]))
            if self.flowline_stop_ids:
                next_up_flat = [id for id in next_up_flat if id not in stop_ids_set]

            # seed the new start point
            from_ids = next_up_flat
            all_from_ids.extend(from_ids)
        if include_wb_permids:
            if not self.flowline_waterbody:
                self.map_flowlines_to_waterbodies()
            # get the waterbody ids for all flowlines in trace (including start) and add to results
            wb_permids_set = {self.flowline_waterbody[id] for id in all_from_ids if id in self.flowline_waterbody}
            wb_permids = list(wb_permids_set.difference(set(self.waterbody_stop_ids))) # if stops present, remove
            all_from_ids.extend(wb_permids)
        return all_from_ids

    def trace_up_from_a_waterbody(self, waterbody_start_id):
        """
        Trace a network upstream of the input waterbody and return the traced network identifiers in a list.

        The lowest flowline segments within the input waterbody will be identified and used to initiate the trace (in
        other words, traces will be found upstream of all waterbody outlets. Waterbodies with no flowline segments
        have an empty trace (are not in their own trace).

        Barriers currently activated on the network will be respected by the trace. The input waterbody will not
        act as a barrier for its own traced network.

        :param waterbody_start_id: Waterbody Permanent_Identifier of flow destination (upstream trace start point).
        :return: List of Permanent_Identifier values for flowlines and waterbodies in the upstream network trace,
        which includes the input waterbody

        """

        # set up the network if necessary
        if not self.upstream:
            self.prepare_upstream()
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        flowline_start_ids = set(self.waterbody_flowline[waterbody_start_id])  # one or more

        # remove waterbody's own flowlines from stop ids--don't want them to stop themselves
        if self.flowline_stop_ids:
            flowline_stop_ids_restore = self.flowline_stop_ids[:]
            waterbody_stop_ids_restore = self.waterbody_stop_ids[:]
            self.flowline_stop_ids = [id for id in self.flowline_stop_ids if id not in flowline_start_ids]
            self.waterbody_stop_ids = [id for id in self.waterbody_stop_ids if id not in waterbody_start_id]
            reset_stops = True
        else:
            reset_stops = False  # use in case all stop ids are erased

        # first identify only the lowest start ids
        next_up = [self.upstream[id] for id in flowline_start_ids]
        next_up_flat = {id for id_list in next_up for id in id_list}
        lowest_flowline_start_ids = flowline_start_ids.difference(next_up_flat)  # lakes may have multiple outlets

        # then trace up for all and flatten result
        unflat_trace_all = [self.trace_up_from_a_flowline(id, True) for id in lowest_flowline_start_ids]
        all_from_ids = list({id for id_list in unflat_trace_all for id in id_list})

        # reset flowline_stop_ids
        if reset_stops:
            self.flowline_stop_ids = flowline_stop_ids_restore[:]
            self.waterbody_stop_ids = waterbody_stop_ids_restore[:]

        return all_from_ids

    def trace_up_from_waterbody_starts(self):
        """
        Trace up from all waterbody start locations currently set on the NHDNetwork instance.

        Barriers currently activated on the network will be respected by the trace. The input waterbodies will not
        act as a barrier for their own traced networks, but will act as barriers for other traces.

        :return Dictionary of traces with key = waterbody Permanent_Identifier, value = list of waterbody and flowline
        Permanent_Identifiers in the traced network.
        :rtype dict
        """
        if self.waterbody_start_ids:
            results = {id: self.trace_up_from_a_waterbody(id) for id in self.waterbody_start_ids}
            return results
        else:
            raise Exception("Populate start IDs with set_start_ids before calling trace_up_from_starts().")

    def trace_10ha_subnetworks(self, exclude_isolated=False):
        """
        Identify the upstream subnetworks of lakes > 10ha for each focal lake in the network's start population.
        :param exclude_isolated: Default False. Whether to exclude isolated lakes (in or out of the focal lake's
        watershed) in the subnetworks for each focal lake.
        :return: Dictionary with key = focal lake id, value = list of subnetwork catchment/flowline/waterbody ids
        """
        if not self.waterbody_start_ids:
            raise Exception("Populate start IDs with set_start_ids before calling trace_up_from_starts().")

        # get all 10ha+ full networks
        initial_start_ids = self.waterbody_start_ids
        self.activate_10ha_lake_stops()
        tenha_ids = self.waterbody_stop_ids
        self.set_start_ids(tenha_ids)
        self.deactivate_stops()
        tenha_traces_no_stops = self.trace_up_from_waterbody_starts()
        if exclude_isolated:
            tenha_traces_no_stops = {k:v for k, v in tenha_traces_no_stops.items() if v}
        self.set_start_ids(initial_start_ids)

        subnetworks = dict()
        for lake_id in self.waterbody_start_ids:
            reset = []
            if lake_id in tenha_traces_no_stops:
                reset = tenha_traces_no_stops[lake_id]
                # temp remove this lake's own network if it's 10ha+
                del tenha_traces_no_stops[lake_id]

            # if this lake id in the trace, then the dict entry is for a downstream lake. discard.
            eligible_tenha_subnets = [v for k, v in tenha_traces_no_stops.items() if lake_id not in v]
            if reset:
                tenha_traces_no_stops[lake_id] = reset
            # get the subnetwork traces that overlap this lake's full network only
            subnetworks[lake_id] = list({id for id_list in eligible_tenha_subnets for id in id_list})

        return subnetworks

    def trace_up_from_hu4_outlets(self):
        if not self.outlets:
            self.identify_outlets()
        results_unflat = [self.trace_up_from_a_flowline(id) for id in self.outlets]
        results = list({id for id_list in results_unflat for id in id_list})
        return results

    def save_trace_catchments(self, trace, output_fc):
        """Select traced features from NHDFlowline and save to output."""
        query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                        for id in trace]))
        output_fc = DM.Select(self.flowline, output_fc, query)
        return output_fc



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
            if lake_permid_flowline: # on network
                lake_permid = lake_permid_flowline

            else: # off network (sink)
                lake_permid = lake_permid_sink
                stream_permid = None

            if nhdplusid in nhd_flowline_dict: # catchment is not for a sink
                stream_permid = nhd_flowline_dict[nhdplusid]
            else: # catchment is for a sink
                stream_permid = None

            # write the update
            new_row = (nhdplusid, lake_permid, stream_permid)
            nhd_cat_copy_cursor.updateRow(new_row)

    return nhd_cat_copy


def merge_lake_catchments(nhdplus_gdb, output_catchments_fc):
    arcpy.env.workspace = 'in_memory'
    catchments_assigned = assign_catchments_to_lakes(nhdplus_gdb, 'catchments_assigned')

    # dissolve the lake catchments and separate out the stream catchments layer
    stream_cats = AN.Select(catchments_assigned, 'stream_cats', 'Lake_PermID IS NULL')
    lake_cats = AN.Select(catchments_assigned, 'lake_cats', 'Lake_PermID IS NOT NULL')
    dissolved_lake_cats = DM.Dissolve(lake_cats, 'dissolved_lake_cats', ['Lake_PermID'])
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
    DM.AddIndex(output_fc, 'Lake_PermID', 'lake_id_idx')
    DM.AddIndex(output_fc, 'Flowline_PermID', 'stream_id_idx')
    DM.Delete('in_memory')
    return output_fc


def calculate_waterbody_strahler(nhdplus_gdb, output_table):
    """Output a table with a new field describing the Strahler stream order for each waterbody in the input GDB.

    The waterbody's Strahler order will be defined as the highest Strahler order for an NHDFlowline artificial
    path associated with that waterbody.

    :param nhdplus_gdb: The NHDPlus HR geodatabase to calculate Strahler values for
    :param output_table: The output table containing lake identifiers and the calculated field "lake_higheststrahler"

    :return: ArcGIS Result object for output_table

    """
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
    # TODO: Eliminate lowest strahler order field, unnecessary
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

    return output_table


def add_waterbody_nhdpid(nhdplus_waterbody_fc, eligible_lakes_fc):
    """
    Transfer waterbody NHDPlusID values from NHDPlus HR geodatabase to another lake/waterbody feature class.

    :param nhdplus_waterbody_fc: NHDWaterbody feature class from an NHDPlus HR geodatabase, containing IDs to transfer
    :param eligible_lakes_fc: A lake/waterbody dataset you want to modify by transferring NHDPlusIDs to a new field.
    :return: ArcGIS Result object for eligible_lakes_fc

    """
    # add field first time
    if not arcpy.ListFields(eligible_lakes_fc, 'NHDPlusID'):
        DM.AddField(eligible_lakes_fc, 'NHDPlusID', 'DOUBLE')

    # get nhdpids
    wbplus_permid_nhdpid = {r[0]:r[1] for r in arcpy.da.SearchCursor(nhdplus_waterbody_fc,
                                                                   ['Permanent_Identifier', 'NHDPlusID'])}

    # transfer nhdpids to the other lakes fc
    with arcpy.da.UpdateCursor(eligible_lakes_fc, ['Permanent_Identifier', 'NHDPlusID']) as u_cursor:
        for row in u_cursor:
            permid, nhdpid = row
            if permid in wbplus_permid_nhdpid:
                nhdpid = wbplus_permid_nhdpid[permid]
            u_cursor.updateRow((permid, nhdpid))

    return eligible_lakes_fc


def update_grid_codes(nhdplus_gdb, output_table):
    """ and save the result as a new table.

    Only lakes over 0.009 sq. km. in area that match the LAGOS lake filter will be added.The features added will be
    slightly more than those that have watersheds created (more inclusive filter) to allow for inadequate precision
    found in the AreaSqKm field.

    :param nhdplus_gdb: The NHDPlus HR geodatabase containing the NHDPlusNHDPlusIDGridCode table to be updated
    :param output_table: A new table that contains the contents of NHDPlusNHDPlusIDGrideCode,
    plus new rows for waterbodies
    :return: ArcGIS Result object for output_table

    """
    # setup
    vpuid = nhdplus_gdb[-16:-12]
    nhdplus_waterbody_fc = os.path.join(nhdplus_gdb, 'NHDWaterbody')
    nhdpid_grid = os.path.join(nhdplus_gdb, 'NHDPlusNHDPlusIDGridCode')
    eligible_clause = 'AreaSqKm > 0.009 AND FCode IN {}'.format(lagosGIS.LAGOS_FCODE_LIST)

    # get IDs to be added
    nhdpids = [r[0] for r in arcpy.da.SearchCursor(nhdplus_waterbody_fc, ['NHDPlusID'], eligible_clause)]

    # start with the next highest grid code
    gridcode = max([r[0] for r in arcpy.da.SearchCursor(nhdpid_grid, 'GridCode')]) + 1
    output_table = DM.CopyRows(nhdpid_grid, output_table)
    i_cursor = arcpy.da.InsertCursor(output_table, ['NHDPlusID', 'SourceFC', 'GridCode', 'VPUID'])

    # insert new rows with new grid codes
    for nhdpid in nhdpids:
        new_row = (nhdpid, 'NHDWaterbody', gridcode, vpuid)
        i_cursor.insertRow(new_row)
        gridcode += 1
    del i_cursor

    return output_table


def add_lake_seeds(nhdplus_catseed_raster, nhdplus_gdb, gridcode_table, eligible_lakes_fc, output_raster, nhdplus_waterbody_fc = ''):
    """
    Modify NHDPlus HR "catseed" raster to include lake-based pour points (seeds) for all lakes in need of watersheds.

    :param str nhdplus_catseed_raster: NHDPlus HR "catseed" TIFF raster for the HU4 needing watersheds created.
    :param str nhdplus_gdb: NHDPlus HR geodatabase for the HU4 needing watersheds created.
    :param str gridcode_table: NHDPlusID-GridCode mapping table (must contain lake seeds) that is the result of
    nhdplushr_tools.update_grid_codes()
    :param str eligible_lakes_fc: Lake feature class containing the lake polygons that will be used as pour points.
    :param str output_raster: Output pour points/seed raster for use in delineating watersheds.
    :param str nhdplus_waterbody_fc: (Optional) If NHDPlusID is not already included in eligible_lakes_fc, specify
    an NHDPlus HR NHDWaterbody feature class to transfer NHDPlusID from
    :return: Path for output_raster

    """
    # not much of a test, if the field exists but isn't populated, this tool will run with no IDs populated
    if not arcpy.ListFields(eligible_lakes_fc, 'NHDPlusID'):
        try:
            add_waterbody_nhdpid(nhdplus_waterbody_fc, eligible_lakes_fc)
        except:
            raise Exception('''
        No NHDPlusID field found in eligible_lakes_fc. Please supply optional nhdplus_waterbody_fc argument using
        the NHDWaterbody feature class for the NHDPlus-HR HUC4 you are trying to process.''')

    arcpy.env.workspace = 'in_memory'
    # essential environment settings for conversion to raster
    arcpy.env.snapRaster = nhdplus_catseed_raster
    arcpy.env.extent = nhdplus_catseed_raster
    arcpy.env.cellSize = nhdplus_catseed_raster
    arcpy.env.outputCoordinateSystem = arcpy.Describe(nhdplus_catseed_raster).spatialReference

    # add gridcodes to lakes
    nhdpid_grid = {r[0]:r[1] for r in arcpy.da.SearchCursor(gridcode_table, ['NHDPlusID', 'GridCode'])}
    this_gdb_wbs = tuple(nhdpid_grid.keys())
    filter_clause = 'NHDPlusID IN {}'.format(this_gdb_wbs)
    eligible_lakes_copy = AN.Select(eligible_lakes_fc, 'eligible_lakes_copy', filter_clause)
    DM.AddField(eligible_lakes_copy, 'GridCode', 'LONG')
    with arcpy.da.UpdateCursor(eligible_lakes_copy, ['NHDPlusID', 'GridCode']) as u_cursor:
        for row in u_cursor:
            new_row = (row[0], nhdpid_grid[row[0]])
            u_cursor.updateRow(new_row)

    # convert lakes
    lake_seeds = arcpy.PolygonToRaster_conversion(eligible_lakes_copy, 'GridCode', 'lake_seeds')

    combined = DM.MosaicToNewRaster([nhdplus_catseed_raster, lake_seeds], arcpy.env.workspace, 'combined',
                         pixel_type='32_BIT_SIGNED', number_of_bands='1', mosaic_method='LAST')
    DM.BuildRasterAttributeTable(combined)

    # due to burn/catseed errors in NHD, we are removing all sinks marked "NHDWaterbody closed lake" (SC)
    # remove from existing raster so we don't have to duplicate their flowline processing steps
    # in regions with no error: no change, correctly indicated closed lakes would be removed but we have overwritten
    # them with our own lake poly seeds anyway.
    sink = os.path.join(nhdplus_gdb, 'NHDPlusSink')
    sinks_to_remove = tuple([r[0] for r in arcpy.da.SearchCursor(sink, ['GridCode'], "PurpCode = 'SC'")])
    arcpy.CheckOutExtension('Spatial')
    if sinks_to_remove:
        nobadsinks = arcpy.sa.SetNull(combined, combined, 'VALUE in {}'.format(sinks_to_remove))
        nobadsinks.save(output_raster)
    else:
        DM.CopyRaster(combined, output_raster)
    arcpy.CheckInExtension('Spatial')

    return output_raster

def fix_hydrodem(hydrodem_raster, lagos_catseed_raster, out_raster):
    """Fills interior NoData values in lakes removed from pour points, so that TauDEM pit remove will fill them."""
    arcpy.env.workspace = 'in_memory'
    # per suggestion by Price here https://community.esri.com/people/curtvprice/blog/2017/03/03/temporary-rasters-in-arcpy
    arcpy.env.scratchWorkspace = os.path.dirname(os.path.dirname(os.path.dirname(lagos_catseed_raster)))
    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension('Spatial')
    dem_null = arcpy.sa.IsNull(hydrodem_raster)
    lagos_null = arcpy.sa.IsNull(lagos_catseed_raster)
    replacement = arcpy.sa.FocalStatistics(hydrodem_raster, statistics_type='MINIMUM') # assign lake elevation value
    result = arcpy.sa.Con((dem_null == 1) & (lagos_null == 1), replacement, hydrodem_raster)
    result.save(out_raster)
    arcpy.CheckInExtension('Spatial')
    arcpy.env.overwriteOutput = False



def delineate_catchments(flowdir_raster, catseed_raster, nhdplus_gdb, gridcode_table, output_fc):
    """
    Delineate local catchments and label them with GridCode, NHDPlusID, SourceFC, and VPUID for the water feature.

    :param flowdir_raster: LAGOS "fdr" TIFF raster for the HU4 needing local catchments delineated.
    :param catseed_raster: Pour points raster, the result of nhdplustools_hr.add_lake_seeds()
    :param nhdplus_gdb: NHDPlus HR geodatabase for the subregion needing local catchments delineated.
    :param gridcode_table: Modified NHDPlusID-GridCode mapping table, the result of nhdplustools_hr.update_grid_codes()
    :param output_fc: Output feature class for the local catchments
    :return: ArcGIS Result object for output_fc

    """
    # establish environments
    arcpy.CheckOutExtension('Spatial')
    arcpy.env.workspace = 'in_memory'
    arcpy.env.snapRaster = flowdir_raster


    # delineate watersheds with ArcGIS Watershed tool, then convert to one polygon per watershed
    arcpy.AddMessage("Delineating watersheds...")
    sheds = arcpy.sa.Watershed(flowdir_raster, catseed_raster, 'Value')
    arcpy.AddMessage("Watersheds complete.")
    sheds_poly = arcpy.RasterToPolygon_conversion(sheds, 'sheds_poly', 'NO_SIMPLIFY', 'Value')
    DM.AlterField(sheds_poly, 'gridcode', 'GridCode', clear_field_alias=True)
    dissolved = DM.Dissolve(sheds_poly, 'dissolved', 'GridCode')
    arcpy.AddMessage("Watersheds converted to vector.")


    # "Join" to the other identifiers via GridCode
    gridcode_dict = {r[0]:r[1:] for r in arcpy.da.SearchCursor(gridcode_table,
                                                                 ['GridCode', 'NHDPlusID', 'SourceFC', 'VPUID'])}
    DM.AddField(dissolved, 'NHDPlusID', 'DOUBLE')
    DM.AddField(dissolved, 'SourceFC', 'TEXT', field_length=20)
    DM.AddField(dissolved, 'VPUID', 'TEXT', field_length=8)
    DM.AddField(dissolved, 'Permanent_Identifier', 'TEXT', field_length = 40)
    DM.AddField(dissolved, 'On_Main_Network', 'TEXT', field_length = 1)

    # add permids to watersheds
    nhd_network = NHDNetwork(nhdplus_gdb)
    if not nhd_network.nhdpid_flowline:
        nhd_network.map_nhdpid_to_flowlines()
    if not nhd_network.nhdpid_waterbody:
        nhd_network.map_waterbody_to_nhdpids()
    nhdpid_combined = defaultdict(list)
    for d in (nhd_network.nhdpid_flowline, nhd_network.nhdpid_waterbody):
        for k, v in d.iteritems():
            nhdpid_combined[k] = v

    on_network = set(nhd_network.trace_up_from_hu4_outlets())

    with arcpy.da.UpdateCursor(dissolved, ['GridCode', 'NHDPlusID', 'SourceFC', 'VPUID', 'Permanent_Identifier', 'On_Main_Network']) as u_cursor:
        for row in u_cursor:
            gridcode, nhdpid, sourcefc, vpuid, permid, onmain = row
            if gridcode != 0:
                nhdpid, sourcefc, vpuid = gridcode_dict[gridcode]
            permid = nhdpid_combined[nhdpid] if nhdpid in nhdpid_combined else None
            onmain = 'Y' if permid in on_network else 'N'
            # permid: if no permid, some kind of sink, None is fine
            u_cursor.updateRow((gridcode, nhdpid, sourcefc, vpuid, permid, onmain))

    output_fc = DM.CopyFeatures(dissolved, output_fc)
    return output_fc


def aggregate_watersheds(catchments_fc, nhdplus_gdb, eligible_lakes_fc, output_fc,
                         mode = ['interlake', 'network', 'both']):
    """
    Accumulate upstream watersheds for all eligible lakes in this subregion and save result as a feature class.

    Interlake watersheds identify upstream lakes greater than 10 hectares in size as sinks and the accumulated
    watershed does not include upstream flow "sunk" into those other lakes.

    Network watersheds accumulate all upstream flow with no barriers, until the HU4 boundary. LAGOS network watersheds
    do not extend across HU4 boundaries even though water physically flows from the upstream HU4 into this one.

    Only lakes found in both the "eligible" lakes feature class and the NHD geodatabase will have watersheds
    delineated in the result. (Permanent_Identifier for the lake in both data sources.)


    :param catchments_fc: The result of nhdplushr_tools.delineate_catchments().
    :param nhdplus_gdb: The NHDPlus HR geodatabase for which watershed accumulations are needed.
    :param eligible_lakes_fc: The input lakes for which watershed accumulations are needed.
    :param output_fc: A feature class containing the (overlapping) accumulated watersheds results
    :param mode: Options = 'network', 'interlake', or 'both. For'interlake' (and 'both'), upstream 10ha+ lakes will
    act as sinks in the focal lake's accumulated watershed. 'both' option will output two feature classes, one
    with name ending 'interlake', and one with name ending 'network'
    :return: ArcGIS Result object(s) for output(s)
    """

    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5070)
    arcpy.env.workspace = 'in_memory'
    temp_gdb = csiutils.create_temp_GDB('aggregate_watersheds')

    # get this huc4
    huc4_code = re.search('\d{4}', os.path.basename(nhdplus_gdb)).group()
    wbd_hu4 = os.path.join(nhdplus_gdb, "WBDHU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause4 = """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhdplus_gdb, field_name), huc4_code)
    hu4 = arcpy.Select_analysis(wbd_hu4, "hu4", whereClause4)

    # initialize the network object and build a dictionary we'll use
    arcpy.AddMessage("Preparing network traces...")
    nhd_network = NHDNetwork(nhdplus_gdb)

    # use temp gdb to make indexed, island-free copy of lakes
    temp_waterbodies = os.path.join(temp_gdb, 'waterbody_holeless')
    # so there's something stupid where ArcGIS doesn't like fields after shape_* but there's no way to move them
    # except to do this
    waterbody_mem = DM.CopyFeatures(nhd_network.waterbody, 'waterbody_mem')
    waterbody_holeless = DM.EliminatePolygonPart(waterbody_mem, temp_waterbodies,
                                                 'PERCENT', part_area_percent = '99')
    DM.AddIndex(waterbody_holeless, 'Permanent_Identifier', 'permid_idx')
    waterbody_lyr = DM.MakeFeatureLayer(waterbody_holeless)

    # have to send watersheds to a temp gdb so we can use an index
    # dropping extra watersheds fields speeds up dissolve 6X, which we NEED
    temp_gdb_watersheds_path = os.path.join(temp_gdb, 'watersheds_simple')
    watersheds_simple = lagosGIS.select_fields(catchments_fc, temp_gdb_watersheds_path, ['Permanent_Identifier'])
    DM.AddIndex(watersheds_simple, 'Permanent_Identifier', 'permid_idx')
    watersheds_lyr = DM.MakeFeatureLayer(watersheds_simple, 'watersheds_lyr')

    # Step 1: intersect eligible_lakes and lakes for this NHD gdb (eligible_lakes can have much larger spatial extent)
    # any lake id that doesn't intersect/inner join will be DROPPED and will not get a watershed traced
    gdb_wb_permids = {row[0] for row in arcpy.da.SearchCursor(nhd_network.waterbody, 'Permanent_Identifier') if row[0]}
    eligible_lake_ids = {row[0] for row in arcpy.da.SearchCursor(eligible_lakes_fc, 'Permanent_Identifier')}
    matching_ids = list(gdb_wb_permids.intersection(eligible_lake_ids))

    # Step 2: If interlake, get traces for all 10ha+ lakes, so they can be identified and
    # erased from interlake watersheds for other (focal) lakes later. If network, do nothing.
    if mode in ('interlake', 'both'):
        # get list of 10ha+ lakes and get their NETWORK traces
        minus_traces = nhd_network.trace_10ha_subnetworks()

    # Step 3: run the desired traces according to the mode. trace[id] = list of all flowline IDS in trace
    nhd_network.set_start_ids(matching_ids)
    traces = nhd_network.trace_up_from_waterbody_starts()

    # Identify inlets
    inlets = set(nhd_network.identify_inlets())
    partial_test = {k:set(v).intersection(inlets) for k,v in traces.items()}

    arcpy.AddMessage("Accumulating watersheds according to traces...")
    counter = 0
    single_catchment_ids = []
    # The specific recipe for speed in this loop (about 0.8 seconds per loop/drainage lake):
    # 1) The watersheds dataset being queried must have an index. (use temp_gdb instead of in_memory above)
    # 2) It is faster to AN.Select from a feature layer of the indexed lake/watershed dataset than the dataset itself.
    # 3) Dissolve must work on something in_memory (not a selected layer on disk) for a big speed increase.
    # 4) Extraneous fields are NOT ignored by Dissolve and slow it down, so they are removed earlier.
    # 5) Spatial queries were actually quite fast but picked up extraneous catchments, so we will not use that method.
    # 6) Deletions in the loop waste time (1/3 second per loop) and overwriting causes no problems.
    # 7) Avoid processing
    arcpy.env.overwriteOutput = True
    arcpy.SetLogHistory(False)
    for lake_id in matching_ids:
        # Loop Step 2: Determine if the lake is on the network. If not, skip accumulation.
        trace_permids = traces[lake_id]
        if len(trace_permids) <= 1:
            single_catchment_ids.append(lake_id)

        else:
            # print updates roughly every 5 minutes
            counter += 1
            if counter % 500 == 0:
                print("{} of {} lakes completed...".format(counter, len(matching_ids)))
            # Loop Step 1: Fetch this lake
            this_lake = AN.Select(waterbody_lyr, 'this_lake', "Permanent_Identifier = '{}'".format(lake_id))

            # Loop Step 2: Select catchments with their Permanent_Identifier in the trace
            flowline_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                             for id in trace_permids]))
            selected_watersheds = AN.Select(watersheds_lyr, 'selected_watersheds', flowline_query)

            # Loop Step 3: If lake has upstream connectivity, dissolve catchments and eliminate holes.
            # Calculate some metrics of the change.
            this_watershed_holes = DM.Dissolve(selected_watersheds, 'this_watershed_holes')  # sheds has selection
            no_holes = DM.EliminatePolygonPart(this_watershed_holes, 'no_holes', 'PERCENT', part_area_percent='99.999')

            # Loop Step 4: Erase the lake from its own shed
            lakeless_watershed = arcpy.Erase_analysis(no_holes, this_lake, 'lakeless_watershed')
            DM.AddField(this_watershed_holes, 'Permanent_Identifier', 'TEXT', field_length=40)
            DM.CalculateField(this_watershed_holes, 'Permanent_Identifier', lake_id, 'PYTHON')

            # Loop Step 5: If interlake and there are things to erase, erase upstream 10ha+ lake subnetworks
            # (after dissolving them to remove holes). This erasing pattern allows us to remove other sinks only.
            if mode in ('interlake', 'both') and minus_traces[lake_id]:

                #select matching watersheds
                tenha_subnetworks_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                 for id in minus_traces[lake_id]]))
                other_tenha = AN.Select(watersheds_lyr, 'other_tenha', tenha_subnetworks_query)

                # since subnetworks can be hole-y due to sinks also, need to dissolve before erasing
                other_tenha_dissolved = DM.Dissolve(other_tenha, 'other_tenha_dissolved')
                other_tenha_holeless = DM.EliminatePolygonPart(other_tenha_dissolved, 'other_tenha_holeless', 'PERCENT',
                                                               part_area_percent='99.999')
                this_watershed = arcpy.Erase_analysis(lakeless_watershed, other_tenha_holeless, 'this_watershed')

            else:
                this_watershed = lakeless_watershed

            # Loop Step 7: Save to results
            if not arcpy.Exists('merged_fc'):
                merged_fc = DM.CopyFeatures(this_watershed, 'merged_fc')
                # to avoid append mismatch due to permanent_identifier
                DM.AlterField(merged_fc, 'Permanent_Identifier', field_length=40)
            else:
                DM.Append(this_watershed, merged_fc, 'NO_TEST')

            if mode == 'both':
                # then lakeless_watershed contains the network shed
                if not arcpy.Exists('merged_fc_both_network'):
                    merged_fc_both_network = DM.CopyFeatures(lakeless_watershed, 'merged_fc_both_network')
                    # to avoid append mismatch due to permanent_identifier
                    DM.AlterField(merged_fc_both_network, 'Permanent_Identifier', field_length=40)
                else:
                    DM.Append(lakeless_watershed, merged_fc_both_network)

    arcpy.env.overwriteOutput = False


    # Step 5: For all isolated lakes, select the correct catchments and erase focal lakes from their own sheds
    # in one operation (to save time in loop above)
    arcpy.AddMessage("Batch processing remaining lakes...")
    if single_catchment_ids:
        waterbodies_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id) for id in single_catchment_ids]))
        these_lakes = AN.Select(waterbody_lyr, 'these_lakes', waterbodies_query)
        watersheds_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                                 for id in single_catchment_ids]))
        these_watersheds = AN.Select(watersheds_simple, 'these_watersheds', watersheds_query)
        lakeless_watersheds = AN.Erase(these_watersheds, these_lakes, 'lakeless_watersheds')

        DM.Append(lakeless_watersheds, merged_fc, 'NO_TEST')
        if mode == 'both':
            DM.Append(lakeless_watersheds, merged_fc_both_network, 'NO_TEST')

    if mode in ('interlake', 'both'):
        # Remove isolated 10 ha sinks--union and select out any where permids unequal (holes). Dissolve back to one.
        # Roundabout way of saying erase 10ha catchments from me EXCEPT my own catchment.
        tenha_local_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                           for id in tenha_start_ids]))
        tenha_watersheds = AN.Select(watersheds_simple, 'tenha_watersheds', tenha_local_query)
        union = AN.Union([merged_fc, tenha_watersheds], 'union')
        sink_drop = AN.Select(union, 'sink_drop',
                              "Permanent_Identifier = Permanent_Identifier_1 OR Permanent_Identifier_1 = ''")
        dissolve_fields = ['Permanent_Identifier',
                           'includeshu4inlet']
        sink_drop_dissolved = DM.Dissolve(sink_drop, 'sink_drop_dissolved', dissolve_fields)
        merged_fc = sink_drop_dissolved
        for item in [tenha_watersheds, union, sink_drop]:
            DM.Delete(item)

    result_fcs = [merged_fc]
    if mode == 'both':
        result_fcs.append(merged_fc_both_network)

    # Fill in all the missing flag values
    for fc in result_fcs:
        with arcpy.da.UpdateCursor(fc, ['Permanent_Identifier', 'includeshu4inlet']) as u_cursor:
            for row in u_cursor:
                permid, inflag = row
                inflag = 'Y' if partial_test[permid] else 'N'
                u_cursor.updateRow((permid, inflag))
        DM.DeleteField(fc, 'ORIG_FID')

    # Clean up results a bit and output. Eliminate slivers smaller than NHD raster cell, clip to HU4, output
    arcpy.SetLogHistory(True)

    refined1 = DM.EliminatePolygonPart(merged_fc, 'refined1', 'AREA', part_area='99', part_option='ANY')
    result1 = AN.Clip(refined1, hu4, output_fc)
    DM.DeleteField(result1, 'ORIG_FID')
    if mode == 'both':
        refined2 = DM.EliminatePolygonPart(merged_fc_both_network, 'refined2', 'AREA',
                                           part_area='99', part_option='ANY')
        result1 = DM.Rename(output_fc, output_fc + '_interlake')
        result2 = AN.Clip(merged_fc_both_network, hu4, output_fc + '_network')
        DM.DeleteField(result2, 'ORIG_FID')
        for item in [merged_fc_both_network, refined2]:
            DM.Delete(item)

    # Delete work: first fcs to free up temp_gdb, then temp_gdb
    for item in [hu4, waterbody_holeless, watersheds_simple, watersheds_lyr, merged_fc]:
        DM.Delete(item)

    DM.Delete(temp_gdb)

    if mode == 'both':
        return (result1, result2)
    else:
        return result1

def watershed_equality(interlake_watershed_fc, network_watershed_fc):
    """Tests whether the interlake and network watersheds are equal and stores result in a flag field for each fc."""
    DM.AddField(interlake_watershed_fc, 'equalsnetwork', 'TEXT', field_length=1)
    DM.AddField(network_watershed_fc, 'equalsiws', 'TEXT', field_length=1)
    iws_area = {r[0]:r[1] for r in arcpy.da.SearchCursor(interlake_watershed_fc, 'Permanent_Identifier', 'SHAPE@area')}
    net_area = {r[0]:r[1] for r in arcpy.da.SearchCursor(network_watershed_fc, 'Permanent_Identifier', 'SHAPE@area')}
    with arcpy.da.UpdateCursor(interlake_watershed_fc, ['Permanent_Identifier','equalsnetwork']) as u_cursor:
        for row in u_cursor:
            permid, flag = row
            area_is_diff = abs(iws_area[permid] - net_area[permid]) < 0.5
            flag = 'N' if area_is_diff else 'Y'
            u_cursor.updateRow((permid, flag))
    with arcpy.da.UpdateCursor(network_watershed_fc, ['Permanent_Identifier','equalsiws']) as u_cursor:
        for row in u_cursor:
            permid, flag = row
            area_is_diff = abs(iws_area[permid] - net_area[permid]) < 0.5
            flag = 'N' if area_is_diff else 'Y'
            u_cursor.updateRow((permid, flag))