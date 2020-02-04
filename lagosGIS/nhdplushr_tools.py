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
    :ivar str catchment: Path for NHDPlusCatchment feature class
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

    def __init__(self, nhd_gdb):
        self.gdb = nhd_gdb
        self.plus = True if arcpy.Exists(os.path.join(self.gdb, 'NHDPlus')) else False
        self.huc4 = re.search('\d{4}', os.path.basename(nhd_gdb)).group()

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
        self.tenha_waterbody_ids = []
        self.upstream = defaultdict(list)
        self.downstream = defaultdict(list)
        self.nhdpid_flowline = defaultdict(list)
        self.flowline_waterbody = defaultdict(list)
        self.waterbody_flowline = defaultdict(list)
        self.waterbody_nhdpid = defaultdict(list)
        self.nhdpid_waterbody = defaultdict(list)
        self.intermit_flowline_ids = set()
        self.inlets = []
        self.outlets = []
        self.exclude_intermittent_flow = False

    def prepare_upstream(self, force=False):
        """Read the geodatabase flow table and collapse into a flow dictionary."""
        if not self.upstream or force:
            self.upstream = defaultdict(list)
            with arcpy.da.SearchCursor(self.flow, [self.from_column, self.to_column]) as cursor:
                for row in cursor:
                    from_id, to_id = row
                    if from_id == '0': # see drop_intermittent_flow
                        self.upstream[to_id] = []
                    elif from_id not in self.intermit_flowline_ids: # see drop_intermittent_flow
                        self.upstream[to_id].append(from_id)
                    else:
                        continue

    def prepare_downstream(self, force=False):
        """Read the geodatabase flow table and collapse into a flow dictionary."""
        if not self.downstream or force:
            self.downstream = defaultdict(list)
            with arcpy.da.SearchCursor(self.flow, [self.from_column, self.to_column]) as cursor:
                for row in cursor:
                    from_id, to_id = row
                    if to_id == '0' :
                        self.downstream[from_id] = []
                    elif to_id not in self.intermit_flowline_ids: # see drop_intermittent_flow
                        self.downstream[from_id].append(to_id)
                    else:
                        continue

    def map_nhdpid_to_flowlines(self):
        """Construct the nhdpid_flowline identifier mapping dictionary."""
        self.nhdpid_flowline = {r[0]: r[1]
                                for r in arcpy.da.SearchCursor(self.flowline, ['NHDPlusID', 'Permanent_Identifier'])}

    def map_waterbody_to_nhdpids(self):
        """Construct the waterbody_nhdpid and nhdpid_waterbody identifier mapping dictionaries."""
        self.waterbody_nhdpid = {r[0]: r[1]
                                 for r in arcpy.da.SearchCursor(self.waterbody, ['Permanent_Identifier', 'NHDPlusID'])}
        self.nhdpid_waterbody = {v: k for k, v in self.waterbody_nhdpid.items()}

    def drop_intermittent_flow(self):
        self.intermit_flowline_ids= {r[0] for r in arcpy.da.SearchCursor(self.flowline,
                                                        ['Permanent_Identifier', 'FCode']) if
                                     r[1] in [46003, 46007]}
        self.exclude_intermittent_flow = True

        # refresh the upstream/downstream dictionaries
        if self.upstream:
            self.prepare_upstream(force=True)
        if self.downstream:
            self.prepare_downstream(force=True)

    def include_intermittent_flow(self):
        self.intermit_flowline_ids = set()
        self.exclude_intermittent_flow = False

        # refresh the upstream/downstream dictionaries
        if self.upstream:
            self.prepare_upstream(force=True)
        if self.downstream:
            self.prepare_downstream(force=True)

    def map_flowlines_to_waterbodies(self):
        """Construct the flowline_waterbody identifier mapping dictionary."""
        self.flowline_waterbody = {r[0]: r[1]
                                   for r in arcpy.da.SearchCursor(self.flowline,
                                                                  ['Permanent_Identifier',
                                                                   'WBArea_Permanent_Identifier'])
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
        # and save stable for re-use by network class
        self.tenha_waterbody_ids = self.waterbody_stop_ids

    def deactivate_stops(self):
        """Deactivate all network barriers (flow proceeds unimpeded through entire network)."""
        self.waterbody_stop_ids = []
        self.flowline_stop_ids = []

    def trace_up_from_a_flowline(self, flowline_start_id, include_wb_permids=True):
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
        limit = len(self.upstream)

        # while there is still network left, iteratively trace up and add on
        while from_ids:
            next_up = [self.upstream[id] for id in from_ids]

            # flatten results
            next_up_flat = set([id for id_list in next_up for id in id_list])
            if self.flowline_stop_ids:
                next_up_flat = next_up_flat.difference(stop_ids_set)

            # seed the new start point
            # if the network size exceeds number of network features, it's because of circular flow
            # de-duplicate trace and make sure from_ids are NEW in that case before proceeding
            if len(all_from_ids) >= limit:
                all_from_ids = list(set(all_from_ids))
                from_ids = next_up_flat.difference(set(all_from_ids))
            # otherwise the trace just walks upstream and records the results of this iteration
            else:
                from_ids = next_up_flat
            all_from_ids.extend(from_ids)

        if include_wb_permids:
            if not self.flowline_waterbody:
                self.map_flowlines_to_waterbodies()
            # get the waterbody ids for all flowlines in trace (including start) and add to results
            wb_permids_set = {self.flowline_waterbody[id] for id in all_from_ids if id in self.flowline_waterbody}
            wb_permids = list(wb_permids_set.difference(set(self.waterbody_stop_ids)))  # if stops present, remove
            all_from_ids.extend(wb_permids)
        return list(set(all_from_ids))

    def trace_down_from_a_flowline(self, flowline_start_id, include_wb_permids=True):
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
        if not self.downstream:
            self.prepare_downstream()
        if self.flowline_stop_ids:
            stop_ids_set = set(self.flowline_stop_ids)

        # get the next IDs down from the start
        to_ids = self.downstream[flowline_start_id]
        all_to_ids = to_ids[:]
        all_to_ids.append(flowline_start_id)  # include start point in trace
        limit = len(self.downstream)

        # while there is still network left, iteratively trace down and add on
        while to_ids:
            next_down = [self.downstream[id] for id in to_ids]

            # flatten results
            next_down_flat = set([id for id_list in next_down for id in id_list])
            if self.flowline_stop_ids:
                next_down_flat = next_down_flat.difference(stop_ids_set)

            # seed the new start point
            # if the network size exceeds number of network features, it's because of circular flow
            # de-duplicate trace and make sure from_ids are NEW in that case before proceeding
            if len(all_to_ids) >= limit:
                all_to_ids = list(set(all_to_ids))
                to_ids = next_down_flat.difference(set(all_to_ids))
            # otherwise the trace just walks upstream and records the results of this iteration
            else:
                to_ids = next_down_flat
            all_to_ids.extend(to_ids)

        if include_wb_permids:
            if not self.flowline_waterbody:
                self.map_flowlines_to_waterbodies()
            # get the waterbody ids for all flowlines in trace (including start) and add to results
            wb_permids_set = {self.flowline_waterbody[id] for id in all_to_ids if id in self.flowline_waterbody}
            wb_permids = list(wb_permids_set.difference(set(self.waterbody_stop_ids)))  # if stops present, remove
            all_to_ids.extend(wb_permids)
        return list(set(all_to_ids))

    def identify_outlets(self):
        """Identify inlets: flowlines that flow in but have no upstream flowline in this gdb."""
        if not self.upstream:
            self.prepare_upstream()

        to_ids = set(self.upstream.keys()).difference({'0'})
        from_all = {f for from_list in self.upstream.values() for f in from_list}
        downstream_inlets = list(set(to_ids).difference(set(from_all)))
        outlets_unflat = [v for k, v in self.upstream.items() if k in downstream_inlets]
        outlets = [o for o_list in outlets_unflat for o in o_list]

        # for subregions with frontal or closed drainage, take the largest network's outlet
        # plus take any outlets with a network at least 1/2 the size of the main one in case there are multiple
        # or in other words, the largest sink possible is 1/3 the hu4 size (by stream segment count)
        if not outlets:
            print("Secondary outlet determination being used due to frontal or closed drainage for the subregion.")
            to_ids = set(self.upstream.keys())
            next_up = [self.upstream[id] for id in to_ids]
            next_up_flat = {id for id_list in next_up for id in id_list}
            lowest_to_ids = list(to_ids.difference(next_up_flat))
            if lowest_to_ids == ['0']:
                lowest_to_ids = self.upstream['0']
            distinct_net_sizes = {id: len(self.trace_up_from_a_flowline(id, max_depth=300)) for id in lowest_to_ids}
            max_net_size = max(distinct_net_sizes.values())
            outlets = [id for id, n in distinct_net_sizes.items() if n >= .5 * max_net_size]
        self.outlets = outlets
        return outlets

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
        which includes the input waterbody if the waterbody is on a network. Empty list if waterbody is isolated.

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

    def trace_down_from_a_waterbody(self, waterbody_start_id):
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
        if not self.downstream:
            self.prepare_downstream()
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

        # first identify only the highest start ids
        next_down = [self.upstream[id] for id in flowline_start_ids]
        next_down_flat = {id for id_list in next_down for id in id_list}
        highest_flowline_start_ids = flowline_start_ids.difference(next_down_flat)  # lakes may have multiple inlets

        # then trace down for all and flatten result
        unflat_trace_all = [self.trace_down_from_a_flowline(id, True) for id in highest_flowline_start_ids]
        all_to_ids = list({id for id_list in unflat_trace_all for id in id_list})

        # reset flowline_stop_ids
        if reset_stops:
            self.flowline_stop_ids = flowline_stop_ids_restore[:]
            self.waterbody_stop_ids = waterbody_stop_ids_restore[:]

        return all_to_ids

    def classify_waterbody_connectivity(self, waterbody_start_id):
        if not self.upstream:
            self.prepare_upstream()
        if not self.downstream:
            self.prepare_upstream()
        if not self.waterbody_flowline:
            self.map_flowlines_to_waterbodies()
        if not self.tenha_waterbody_ids:
            self.activate_10ha_lake_stops()
            self.deactivate_stops()

        # Isolated first
        trace_up = self.trace_up_from_a_waterbody(waterbody_start_id)
        trace_down = self.trace_down_from_a_waterbody(waterbody_start_id)
        if len(trace_up) == 0 and len(trace_down) == 0 and not self.exclude_intermittent_flow:
            connclass = 'Isolated'
        # otherwise subtract lake's self and internal flowlines, check for 10 ha lakes in trace, and classify
        else:
            inside_ids = self.waterbody_flowline[waterbody_start_id]
            inside_ids.append(waterbody_start_id)
            nonself_trace_down = set(trace_down).difference(set(inside_ids))
            nonself_trace_up = set(trace_up).difference(set(inside_ids))
            tenha_upstream = set(nonself_trace_up).intersection(set(self.tenha_waterbody_ids))

            if len(nonself_trace_up) == 0:
                if len(nonself_trace_down) > 0:
                    connclass = 'Headwater'
                if len(nonself_trace_down) == 0:
                    connclass = 'Isolated'
            elif tenha_upstream:
                connclass = 'DrainageLk'
            else:
                connclass = 'Drainage'
        return connclass

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
        tenha_traces_no_stops_lists = self.trace_up_from_waterbody_starts()
        tenha_traces_no_stops = {k: set(v) for k, v in tenha_traces_no_stops_lists.items()}
        isolated_tenha = [k for k, v in tenha_traces_no_stops.items() if not v]
        # reset start ids to whatever they were before method invoked
        self.set_start_ids(initial_start_ids)
        full_traces = self.trace_up_from_waterbody_starts()

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
            full_trace = set(full_traces[lake_id])
            if full_trace:
                sub_traces = {id for id_list in eligible_tenha_subnets for id in id_list}
                subnetwork = list(full_trace.intersection(sub_traces))
            else:
                subnetwork = []

            # will add ALL isolated lakes back in, not just those in this region/full-trace
            if not exclude_isolated:
                if lake_id in isolated_tenha:
                    other_tenha_ids = [id for id in isolated_tenha if id != lake_id]
                else:
                    other_tenha_ids = isolated_tenha[:]
                subnetwork.extend(other_tenha_ids)
            subnetworks[lake_id] = subnetwork

        return subnetworks

    def trace_up_from_hu4_outlets(self):
        """ Trace all of the main network, starting from the subregion outlets."""
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
    DM.AddField(nhd_cat_copy, 'Lake_PermID', field_type='TEXT', field_length=40)
    DM.AddField(nhd_cat_copy, 'Flowline_PermID', field_type='TEXT', field_length=40)

    # build dictionaries for the joins
    nhd_flowline_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
                                                                   ['NHDPlusID', 'Permanent_Identifier'])}
    nhd_wbarea_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
                                                                 ['NHDPlusID', 'WBArea_Permanent_Identifier'])}
    nhd_wb_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_wb, ['NHDPlusID', 'Permanent_Identifier'])}
    valid_wb_ids = set(nhd_wb_dict.values())
    # some WBArea_... values come from NHDArea polygons, not NHDWaterbody. Filter dictionary for valid only.
    flowline_wb_dict = {nhdplusid: nhd_wbarea_dict[nhdplusid] for nhdplusid, wb_permid in nhd_wbarea_dict.items() if
                        wb_permid in valid_wb_ids}

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
            if lake_permid_flowline:  # on network
                lake_permid = lake_permid_flowline

            else:  # off network (sink)
                lake_permid = lake_permid_sink
                stream_permid = None

            if nhdplusid in nhd_flowline_dict:  # catchment is not for a sink
                stream_permid = nhd_flowline_dict[nhdplusid]
            else:  # catchment is for a sink
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
    DM.AddField(dissolved_lake_cats, 'NHDPlusID', 'DOUBLE')  # leave as all NULL on purpose

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
                                                                   ['NHDPlusID', 'WBArea_Permanent_Identifier']) if
                         r[1]}
    # filter out flowlines we can't get strahler for NOW, so that loop below doesn't have to test
    nhd_vaa_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_vaa, ['NHDPlusID', 'StreamOrde'])
                    if r[0] in nhd_flowline_dict}
    # filter out lines with uninitialized flow as they don't appear in nhd_vaa_dict
    nhd_flowline_dict2 = {key: val for key, val in nhd_flowline_dict.items() if key in nhd_vaa_dict}

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
    wbplus_permid_nhdpid = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhdplus_waterbody_fc,
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
    """Add lakes to gridcode table and save the result as a new table.

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


def add_lake_seeds(nhdplus_catseed_raster, nhdplus_gdb, gridcode_table, eligible_lakes_fc, output_raster,
                   nhdplus_waterbody_fc=''):
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
    nhdpid_grid = {r[0]: r[1] for r in arcpy.da.SearchCursor(gridcode_table, ['NHDPlusID', 'GridCode'])}
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
    sinks_to_remove = [r[0] for r in arcpy.da.SearchCursor(sink, ['GridCode'], "PurpCode = 'SC'")]
    arcpy.CheckOutExtension('Spatial')
    if sinks_to_remove:
        nobadsinks = arcpy.sa.SetNull(combined, combined, 'VALUE in ({})'.format(','.join(['{}'.format(id)
                                                                                           for id in sinks_to_remove])))
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
    replacement = arcpy.sa.FocalStatistics(hydrodem_raster, statistics_type='MINIMUM')  # assign lake elevation value
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
    arcpy.env.extent = flowdir_raster
    nhd_network = NHDNetwork(nhdplus_gdb)

    # delineate watersheds with ArcGIS Watershed tool, then convert to one polygon per watershed
    arcpy.AddMessage("Delineating watersheds...")
    sheds = arcpy.sa.Watershed(flowdir_raster, catseed_raster, 'Value')
    arcpy.AddMessage("Watersheds complete.")
    sheds_poly = arcpy.RasterToPolygon_conversion(sheds, 'sheds_poly', 'NO_SIMPLIFY', 'Value')
    DM.AlterField(sheds_poly, 'gridcode', 'GridCode', clear_field_alias=True)
    dissolved = DM.Dissolve(sheds_poly, 'dissolved', 'GridCode')
    arcpy.AddMessage("Watersheds converted to vector.")

    # "Join" to the other identifiers via GridCode
    update_fields = ['GridCode', 'NHDPlusID', 'SourceFC', 'VPUID']
    if not nhd_network.plus:
        update_fields.append('Permanent_Identifier')
    gridcode_dict = {r[0]: r[1:] for r in arcpy.da.SearchCursor(gridcode_table, update_fields)}
    DM.AddField(dissolved, 'NHDPlusID', 'DOUBLE')
    DM.AddField(dissolved, 'SourceFC', 'TEXT', field_length=20)
    DM.AddField(dissolved, 'VPUID', 'TEXT', field_length=8)
    DM.AddField(dissolved, 'Permanent_Identifier', 'TEXT', field_length=40)
    DM.AddField(dissolved, 'On_Main_Network', 'TEXT', field_length=1)

    # add permids to watersheds for NHDPlus

    if nhd_network.plus:
        if not nhd_network.nhdpid_flowline:
            nhd_network.map_nhdpid_to_flowlines()
        if not nhd_network.nhdpid_waterbody:
            nhd_network.map_waterbody_to_nhdpids()
        nhdpid_combined = defaultdict(list)
        for d in (nhd_network.nhdpid_flowline, nhd_network.nhdpid_waterbody):
            for k, v in d.iteritems():
                nhdpid_combined[k] = v

    on_network = set(nhd_network.trace_up_from_hu4_outlets())

    print('Adding identifiers to dissolved watersheds...')
    with arcpy.da.UpdateCursor(dissolved, ['GridCode', 'NHDPlusID', 'SourceFC', 'VPUID', 'Permanent_Identifier',
                                           'On_Main_Network']) as u_cursor:
        for row in u_cursor:
            gridcode, nhdpid, sourcefc, vpuid, permid, onmain = row
            if gridcode != 0:
                if nhd_network.plus:
                    nhdpid, sourcefc, vpuid = gridcode_dict[gridcode]
                else:
                    nhdpid, sourcefc, vpuid, permid = gridcode_dict[gridcode]
            if not permid:
                permid = nhdpid_combined[nhdpid] if nhdpid in nhdpid_combined else None
            onmain = 'Y' if permid in on_network else 'N'
            u_cursor.updateRow((gridcode, nhdpid, sourcefc, vpuid, permid, onmain))

    output_fc = DM.CopyFeatures(dissolved, output_fc)
    return output_fc


def aggregate_watersheds(catchments_fc, nhd_gdb, eligible_lakes_fc, output_fc,
                         mode=['interlake', 'network']):
    """
    Accumulate upstream watersheds for all eligible lakes in this subregion and save result as a feature class.

    Interlake watersheds identify upstream lakes greater than 10 hectares in size as sinks and the accumulated
    watershed does not include upstream flow "sunk" into those other lakes.

    Network watersheds accumulate all upstream flow with no barriers, until the HU4 boundary. LAGOS network watersheds
    do not extend across HU4 boundaries even though water physically flows from the upstream HU4 into this one.

    Only lakes found in both the "eligible" lakes feature class and the NHD geodatabase will have watersheds
    delineated in the result. (Permanent_Identifier for the lake in both data sources.)


    :param catchments_fc: The result of nhdplushr_tools.delineate_catchments().
    :param nhd_gdb: The NHDPlus HR or NHD HR geodatabase for which watershed accumulations are needed.
    :param eligible_lakes_fc: The input lakes for which watershed accumulations are needed.
    :param output_fc: A feature class containing the (overlapping) accumulated watersheds results
    :param mode: Options = 'network', 'interlake', or 'both. For'interlake' (and 'both'), upstream 10ha+ lakes will
    act as sinks in the focal lake's accumulated watershed. 'both' option will output two feature classes, one
    with name ending 'interlake', and one with name ending 'network'
    :return: ArcGIS Result object(s) for output(s)
    """

    # setup
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5070)
    arcpy.env.workspace = 'in_memory'
    temp_gdb = csiutils.create_temp_GDB('aggregate_watersheds')

    arcpy.AddMessage("Copying selections from inputs...")
    # extract only this HU4 to use for final clip
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()
    wbd_hu4 = os.path.join(nhd_gdb, "WBDHU4")
    field_name = 'HUC4'
    whereClause4 = """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc4_code)
    hu4 = arcpy.Select_analysis(wbd_hu4, "hu4", whereClause4)

    # Step 1: Intersect eligible_lakes and lakes for this NHD gdb (eligible_lakes can have much larger spatial extent).
    # Any lake id that doesn't intersect/inner join will be DROPPED and will not get a watershed traced
    nhd_network = NHDNetwork(nhd_gdb)
    gdb_wb_permids = {row[0] for row in arcpy.da.SearchCursor(nhd_network.waterbody, 'Permanent_Identifier') if row[0]}
    eligible_lake_ids = {row[0] for row in arcpy.da.SearchCursor(eligible_lakes_fc, 'Permanent_Identifier')}
    matching_ids = list(gdb_wb_permids.intersection(eligible_lake_ids))

    # -----Use temp GDB to create both waterbodies and watersheds copies that are INDEXED then accessed as layer
    # -----Dropping extra fields speeds up dissolve greatly
    # waterbodies copy

    temp_waterbodies = os.path.join(temp_gdb, 'waterbody_holeless')
    subregion_wb_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id) for id in matching_ids]))
    waterbody_mem = AN.Select(nhd_network.waterbody, 'waterbody_mem', subregion_wb_query)
    waterbody_holeless = DM.EliminatePolygonPart(waterbody_mem, temp_waterbodies,
                                                 'PERCENT', part_area_percent='99')
    DM.AddIndex(waterbody_holeless, 'Permanent_Identifier', 'permid_idx')
    waterbody_lyr = DM.MakeFeatureLayer(waterbody_holeless)

    # watersheds copy
    temp_gdb_watersheds_path = os.path.join(temp_gdb, 'watersheds_simple')
    watersheds_simple = lagosGIS.select_fields(catchments_fc, temp_gdb_watersheds_path, ['Permanent_Identifier'])
    DM.AddIndex(watersheds_simple, 'Permanent_Identifier', 'permid_idx')
    watersheds_lyr1 = DM.MakeFeatureLayer(watersheds_simple, 'watersheds_lyr1')  # no "interactive" selections
    watersheds_lyr2 = DM.MakeFeatureLayer(watersheds_simple, 'watersheds_lyr2')

    # Step 2: If interlake, get traces for all 10ha+ lakes, so they can be erased while other sinks are dissolved in.
    #  If network, do nothing.
    arcpy.AddMessage("Preparing network traces...")
    nhd_network.set_start_ids(matching_ids)
    if mode == 'interlake':
        minus_traces = nhd_network.trace_10ha_subnetworks()  # traces to be erased in any event
        nhd_network.activate_10ha_lake_stops()

    # Step 3: Run the desired traces according to the mode. trace[id] = list of all flowline IDS in trace
    traces = nhd_network.trace_up_from_waterbody_starts()

    arcpy.AddMessage("Accumulating watersheds according to traces...")
    counter = 0
    single_catchment_ids = []
    # The specific recipe for speed in this loop (about 0.8 seconds per loop/drainage lake):
    # 1) The watersheds dataset being queried must have an index. (use temp_gdb instead of in_memory above)
    # 2) It is faster to AN.Select from a feature layer of the indexed lake/watershed dataset than the dataset itself.
    # 3) Dissolve must work on something in_memory (not a selected layer on disk) for a big speed increase.
    # 4) Extraneous fields are NOT ignored by Dissolve and slow it down, so they were removed earlier.
    # 5) Spatial queries were actually quite fast but picked up extraneous catchments, so we will not use that method.
    # 6) Deletions in the loop waste time (1/3 second per loop) and overwriting causes no problems.
    # 7) Avoid processing any isolated or headwater lakes, no upstream aggregation necessary.
    arcpy.env.overwriteOutput = True
    arcpy.SetLogHistory(False)
    for lake_id in matching_ids:
        # Loop Step 1: Determine if the lake has upstream network. If not, skip accumulation.
        trace_permids = traces[lake_id]
        if len(trace_permids) <= 2:  # headwater lakes have trace length = 2 (lake and flowline)
            single_catchment_ids.append(lake_id)

        else:
            # *print updates roughly every 5 minutes
            counter += 1
            if counter % 250 == 0:
                print("{} of {} lakes completed...".format(counter, len(matching_ids)))
            # Loop Step 2: Fetch this lake
            this_lake = AN.Select(waterbody_lyr, 'this_lake', "Permanent_Identifier = '{}'".format(lake_id))

            # Loop Step 3: Select catchments with their Permanent_Identifier in the lake's upstream network trace.
            watersheds_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                               for id in trace_permids]))
            selected_watersheds = AN.Select(watersheds_lyr1, 'selected_watersheds', watersheds_query)

            # Loop Step 4: Make a single, hole-free catchment polygon.
            this_watershed_holes = DM.Dissolve(selected_watersheds, 'this_watershed_holes')  # sheds has selection
            no_holes = DM.EliminatePolygonPart(this_watershed_holes, 'no_holes', 'PERCENT', part_area_percent='99.999')

            # Loop Step 5: Erase the lake from its own shed.
            lakeless_watershed = arcpy.Erase_analysis(no_holes, this_lake, 'lakeless_watershed')
            DM.AddField(lakeless_watershed, 'Permanent_Identifier', 'TEXT', field_length=40)
            with arcpy.da.UpdateCursor(lakeless_watershed, 'Permanent_Identifier') as u_cursor:
                for row in u_cursor:
                    u_cursor.updateRow([lake_id])
            # DM.CalculateField(lakeless_watershed, 'Permanent_Identifier', """'{}'""".format(lake_id), 'PYTHON')

            # Loop Step 5: If interlake mode and there are things to erase, erase upstream 10ha+ lake subnetworks.
            # Create dissolved, hole-free subnetwork polygons before erasing.
            # This erasing pattern allows us to remove other sinks only.
            if mode == 'interlake' and minus_traces[lake_id]:

                # Loop Step 5a: Select matching subnetwork watersheds (note: will include isolated).
                tenha_subnetworks_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                                          for id in
                                                                                          minus_traces[lake_id]]))
                DM.SelectLayerByAttribute(watersheds_lyr2, 'NEW_SELECTION', tenha_subnetworks_query)
                DM.SelectLayerByLocation(watersheds_lyr2, 'INTERSECT', lakeless_watershed,
                                         selection_type='SUBSET_SELECTION')

                erase_count = int(DM.GetCount(watersheds_lyr2).getOutput(0))
                if erase_count == 0:
                    this_watershed = lakeless_watershed
                else:
                    # Loop Step 5b: Make a single, hole-free polygon for each subnetwork.
                    other_tenha = DM.CopyFeatures(watersheds_lyr2,
                                                  'other_tenha')  # makes dissolve faster, weird but true
                    other_tenha_dissolved = DM.Dissolve(other_tenha, 'other_tenha_dissolved')
                    other_tenha_holeless = DM.EliminatePolygonPart(other_tenha_dissolved, 'other_tenha_holeless',
                                                                   'PERCENT',
                                                                   part_area_percent='99.999')

                    # Loop Step 5c: Erase the subnetworks.
                    this_watershed = arcpy.Erase_analysis(lakeless_watershed, other_tenha_holeless, 'this_watershed')

                    # *handles a rare situation where a catchment entirely surrounded by isolated 10ha lakes can be
                    # erased by its own shed.
                    if int(DM.GetCount(this_watershed).getOutput(0)) == 0:
                        safe_erase = arcpy.Erase_analysis(other_tenha_holeless, this_watershed_holes, 'safe_erase')
                        this_watershed = arcpy.Erase_analysis(lakeless_watershed, safe_erase, 'this_watershed')
            else:
                this_watershed = lakeless_watershed

            # Loop Step 6: Save current watershed to merged results feature class.
            if not arcpy.Exists('merged_fc'):
                merged_fc = DM.CopyFeatures(this_watershed, 'merged_fc')
                # to avoid append mismatch due to permanent_identifier
                DM.AlterField(merged_fc, 'Permanent_Identifier', field_length=40)
            else:
                DM.Append(this_watershed, merged_fc, 'NO_TEST')

    arcpy.env.overwriteOutput = False

    # Step 4: For all isolated lakes, select the correct catchments and erase focal lakes from their own sheds
    # in one operation (to save time in loop).
    arcpy.AddMessage("Batch processing remaining lakes...")
    if single_catchment_ids:
        waterbodies_query = 'Permanent_Identifier IN ({})'.format(
            ','.join(['\'{}\''.format(id) for id in single_catchment_ids]))
        these_lakes = AN.Select(waterbody_lyr, 'these_lakes', waterbodies_query)
        watersheds_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                           for id in single_catchment_ids]))
        these_watersheds = AN.Select(watersheds_simple, 'these_watersheds', watersheds_query)
        lakeless_watersheds = AN.Erase(these_watersheds, these_lakes, 'lakeless_watersheds')
        DM.Append(lakeless_watersheds, merged_fc, 'NO_TEST')
        for item in [these_lakes, these_watersheds, lakeless_watersheds]:
            DM.Delete(item)

    # Step 5: Fix in-island lakes, if any are present in the subregion. (140 lakes in U.S., in 53 subregions)
    out_count = int(DM.GetCount(merged_fc).getOutput(0))
    if out_count < len(matching_ids):
        # erase original lakes from filled ones = island polygons
        islands = AN.Erase(waterbody_holeless, waterbody_mem, 'islands')
        islands_holeless = DM.EliminatePolygonPart(islands, 'islands_holeless', 'PERCENT', part_area_percent='99')
        islands_lyr = DM.MakeFeatureLayer(islands_holeless, 'islands_lyr')
        # select those filled lakes that are entirely within the island polygons and process their sheds.
        DM.SelectLayerByLocation(waterbody_lyr, 'COMPLETELY_WITHIN', islands_lyr)
        DM.SelectLayerByLocation(watersheds_lyr2, 'INTERSECT', waterbody_lyr)
        # get waterbody catchments only (no island stream catchments
        DM.SelectLayerByAttribute(watersheds_lyr2, 'SUBSET_SELECTION', watersheds_query)
        island_sheds = AN.Erase(watersheds_lyr2, waterbody_lyr, 'island_sheds')  # SELECTION ON both
        DM.Append(island_sheds, merged_fc, 'NO_TEST')
        for item in [islands, islands_holeless, islands_lyr, island_sheds]:
            DM.Delete(item)

    # Step 6: Identify inlets and flag whether each watershed extends to include one.
    inlets = set(nhd_network.identify_inlets())
    partial_test = {k: set(v).intersection(inlets) for k, v in traces.items()}
    DM.AddField(merged_fc, 'includeshu4inlet', 'TEXT', field_length=1)
    with arcpy.da.UpdateCursor(merged_fc, ['Permanent_Identifier', 'includeshu4inlet']) as u_cursor:
        for row in u_cursor:
            permid, inflag = row
            inflag = 'Y' if partial_test[permid] else 'N'
            u_cursor.updateRow((permid, inflag))

    # Step 7: Clean up results a bit and output results: eliminate slivers smaller than NHD raster cell, clip to HU4
    arcpy.SetLogHistory(True)
    refined = DM.EliminatePolygonPart(merged_fc, 'refined1', 'AREA', part_area='99', part_option='ANY')
    result = AN.Clip(refined, hu4, output_fc)
    try:
        DM.DeleteField(result, 'ORIG_FID')
    except:
        pass

    # DELETE/CLEANUP: first fcs to free up temp_gdb, then temp_gdb
    for item in [waterbody_lyr, watersheds_lyr1, watersheds_lyr2,
                 hu4, waterbody_mem, waterbody_holeless, watersheds_simple,
                 merged_fc, refined]:
        DM.Delete(item)
    DM.Delete(temp_gdb)

    # TODO: Delete after confirming none missing
    final_count = int(DM.GetCount(result).getOutput(0))
    if final_count < len(matching_ids):
        output_ids = {r[0] for r in arcpy.da.SearchCursor(output_fc, 'Permanent_Identifier')}
        missing = list(set(matching_ids).difference(output_ids))
        arcpy.AddWarning("The following lakes do not have watersheds in the output: {}".format('\n'.join(missing)))
    return result


def watershed_equality(interlake_watershed_fc, network_watershed_fc):
    """Tests whether the interlake and network watersheds are equal and stores result in a flag field for each fc."""
    try:
        DM.AddField(interlake_watershed_fc, 'equalsnetwork', 'TEXT', field_length=1)
    except:
        pass
    try:
        DM.AddField(network_watershed_fc, 'equalsiws', 'TEXT', field_length=1)
    except:
        pass
    iws_area = {r[0]: r[1] for r in
                arcpy.da.SearchCursor(interlake_watershed_fc, ['Permanent_Identifier', 'SHAPE@area'])}
    net_area = {r[0]: r[1] for r in arcpy.da.SearchCursor(network_watershed_fc, ['Permanent_Identifier', 'SHAPE@area'])}
    with arcpy.da.UpdateCursor(interlake_watershed_fc, ['Permanent_Identifier', 'equalsnetwork']) as u_cursor:
        for row in u_cursor:
            permid, flag = row
            if permid in iws_area and permid in net_area:
                area_is_diff = abs(iws_area[permid] - net_area[permid]) >= 10  # meters square, or 0.01 hectares
                flag = 'N' if area_is_diff else 'Y'
            u_cursor.updateRow((permid, flag))
    with arcpy.da.UpdateCursor(network_watershed_fc, ['Permanent_Identifier', 'equalsiws']) as u_cursor:
        for row in u_cursor:
            permid, flag = row
            if permid in iws_area and permid in net_area:
                area_is_diff = abs(iws_area[permid] - net_area[permid]) >= 10  # square meters
                flag = 'N' if area_is_diff else 'Y'
            u_cursor.updateRow((permid, flag))


def qa_shape_metrics(interlake_watershed_fc, network_watershed_fc, lakes_fc):
    for fc in [interlake_watershed_fc, network_watershed_fc]:
        try:
            DM.AddField(fc, 'isoperimetric', 'DOUBLE')
        except:
            pass
        try:
            DM.AddField(fc, 'perim_area_ratio', 'DOUBLE')
        except:
            pass
        try:
            DM.AddField(fc, 'lake_shed_area_ratio', 'DOUBLE')
        except:
            pass
        lake_areas = {r[0]: r[1] for r in
                      arcpy.da.SearchCursor(lakes_fc, ['Permanent_Identifier', 'lake_waterarea_ha'])}
        with arcpy.da.UpdateCursor(fc, ['isoperimetric', 'perim_area_ratio',
                                        'lake_shed_area_ratio', 'Permanent_Identifier', 'SHAPE@']) as u_cursor:
            for row in u_cursor:
                iso, pa, lakeshed, id, shape = row
                iso = (4 * 3.14159 * shape.area) / (shape.length ** 2)
                pa = shape.length / shape.area
                lakeshed = lake_areas[id] * 10000 / shape.area  # convert lake area to m2
                u_cursor.updateRow((iso, pa, lakeshed, id, shape))


# tools for alternate workflow (non-NHDPlus)
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


def calc_subtype_flag(nhd_gdb, interlake_fc, fits_naming_standard=True):
    if fits_naming_standard:
        permid = 'ws_permanent_identifier'
        eq = 'ws_equalsnws'
        vpuid = 'ws_vpuid'

    else:
        permid = 'Permanent_Identifier'
        eq = 'equalsnetwork'
        vpuid = 'VPUID'

    # Get list of eligible lakes
    nhd_network = NHDNetwork(nhd_gdb)
    gdb_wb_permids = {row[0] for row in arcpy.da.SearchCursor(nhd_network.waterbody, 'Permanent_Identifier') if row[0]}
    eligible_lake_ids = {row[0] for row in arcpy.da.SearchCursor(interlake_fc, permid)}
    matching_ids = list(gdb_wb_permids.intersection(eligible_lake_ids))

    matching_ids_query = '{} IN ({})'.format(permid, ','.join(['\'{}\''.format(id) for id in matching_ids]))
    interlake_fc_mem = arcpy.Select_analysis(interlake_fc, 'in_memory/interlake_fc', matching_ids_query)

    # Pick up watershed equality flag
    print('read eq flag')
    try:
        equalsnetwork = {r[0]: r[1] for r in arcpy.da.SearchCursor(interlake_fc_mem, [permid, eq])}
    except:
        print('Run the watershed_equality function to calculate the equalsnetwork flag before using this tool.')
        raise

    # Run traces
    print('trace')
    nhd_network.set_start_ids(matching_ids)
    traces = nhd_network.trace_up_from_waterbody_starts()

    # Step 4: Calculate sub-types
    def label_subtype(trace, equalsnetwork):
        if len(trace) <= 2:
            return 'LC'
        elif equalsnetwork == 'N':
            return 'IDWS'
        else:
            return 'DWS'

    print('calc results')
    subtype_results = {k: label_subtype(v, equalsnetwork[k]) for k, v in traces.items()}

    if not arcpy.ListFields(interlake_fc, 'ws_subtype'):
        DM.AddField(interlake_fc, 'ws_subtype', 'TEXT', field_length=4)

    with arcpy.da.UpdateCursor(interlake_fc, [permid, vpuid, 'ws_subtype'], matching_ids_query) as u_cursor:
        for row in u_cursor:
            new_result = subtype_results[row[0]]
            vpuid_val = row[1]
            if vpuid_val == nhd_network.huc4:  # only update if the catchment came from the corresponding VPUID
                row[2] = new_result
            u_cursor.updateRow(row)

    DM.Delete('in_memory/interlake_fc')
    return (subtype_results)
