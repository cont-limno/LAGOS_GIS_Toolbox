# filename: NHDNetwork.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (NOT IN ArcGIS Toolbox)


import os
import re
from collections import defaultdict

import arcpy
from arcpy import management as DM

import lagosGIS


class NHDNetwork:
    """

    Class for rapidly assessing network connectivity within an NHD HR or NHDPlus HR geodatabase. This class provides a
    set of methods for working with NHD HR and NHDPlus HR features for multiple applications beyond the LAGOS database
    creation. Most of the methods return Python objects for future work rather than GIS files saved on disk, with the
    exception of save_trace_catchments. Most operations run in less than 2 minutes per subregion.

    :param str nhd_gdb: An NHD or NHDPlus HR geodatabase containing the network information.

    Attributes
    ----------
    :ivar str gdb: NHD or NHDPlus geodatabase assigned to the instance
    :ivar bool plus: Whether the NHD geodatabase is from the bare NHD or the NHDPlus
    :ivar str huc4: 4-digit hydrologic unit code for the NHD geodatabase
    :ivar str from_column: NHDFlow column used to identify inflowing segments
    :ivar str to_column: NHDFlow column used to identify outflowing segments
    :ivar str flow: Path for NHDPlusFLow or NHDFlow table
    :ivar str catchment: Path for NHDPlusCatchment feature class
    :ivar str sink: Path for NHDPlusSink feature class
    :ivar str waterbody: Path for NHDWaterbody feature class
    :ivar str flowline: Path for NHDFLowline feature class
    :ivar list waterbody_start_ids: List of Permanent_Identifiers for waterbodies set as network tracing start locations
    :ivar list flowline_start_ids: List of Permanent_Identifiers for waterbodies set as network tracing start locations
    :ivar list flowline_stop_ids: List of Permanent_Identifiers for waterbodies set as network tracing stop locations
    :ivar list waterbody_stop_ids: List of Permanent_Identifiers for waterbodies set as network tracing stop locations
    :ivar list tenha_waterbody_ids:List of Permanent_Identifiers for waterbodies defined as greater than 10 hectares
    :ivar dict upstream: Dictionary with key = to_id, value = list of from_ids, created from NHDFlow
    :ivar dict downstream: Dictionary with key = from_id, value = list of to_ids, created from NHDFlow
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
    :ivar set intermit_flowline_ids: Set of Permanent_Identifiers for NHDFlowlines assigned intermittent FCodes 46003,
    46007
    :ivar list inlets: List of Permanent_Identifiers for NHDFlowlines that flow in but have no upstream flowline in this
    gdb
    :ivar list outlets: List of Permanent_Identifiers for NHDFlowlines that flow out but have no downstream flowline in
    this gdb
    :ivar bool exclude_intermittent_flow: Whether to exclude (True) or include (False) intermittent flow in the network,
    defaults to False
    :ivar dict lakes_areas: Dictionary with key = lake Permanent_Identifier, value = AreaSqKm. Defines lake population.
    :ivar str lagos_pop_path Path to pre-defined lake census population feature class, if available on local machine.

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
        self.lakes_areas = {}
        # the following should have no effect on other users besides LAGOS use,
        # but will be used to modify .define_lakes so that it includes any permanent_id
        # found in the LAGOS population, regardless of its size or FType in NHDPlus Plus HR
        self.lagos_pop_path = r'D:\Continental_Limnology\Data_Working\LAGOS_US_GIS_Data_v0.6.gdb\Lakes\LAGOS_US_All_Lakes_1ha'

    # ---UTILITIES FOR HIGHER METHODS-----------------------------------------------------------------------------------
    def prepare_upstream(self, force_refresh=False):
        """
        Read the geodatabase flow table and collapse into a flow dictionary, if the flow dictionary was not already
        generated.
        :param bool force_refresh: Force the function to re-generate the flow dictionary, even if it already exists.
        :return: self.upstream
        """
        """Read the geodatabase flow table and collapse into a flow dictionary."""
        if not self.upstream or force_refresh:
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
        return self.upstream

    def prepare_downstream(self, force_refresh=False):
        """Read the geodatabase flow table and collapse into a flow dictionary.

        :param force_refresh: Force the function to re-generate the flow dictionary, even if it already exists.
        :return: self.downstream
        """
        if not self.downstream or force_refresh:
            self.downstream = defaultdict(list)
            with arcpy.da.SearchCursor(self.flow, [self.from_column, self.to_column]) as cursor:
                for row in cursor:
                    from_id, to_id = row
                    if to_id == '0':
                        self.downstream[from_id] = []
                    elif to_id not in self.intermit_flowline_ids: # see drop_intermittent_flow
                        self.downstream[from_id].append(to_id)
                    else:
                        continue
        return self.downstream

    def map_nhdpid_to_flowlines(self):
        """
        Construct the nhdpid_flowline identifier mapping dictionary.
        :return: self.nhdpid_flowline
        """
        self.nhdpid_flowline = {r[0]: r[1]
                                for r in arcpy.da.SearchCursor(self.flowline, ['NHDPlusID', 'Permanent_Identifier'])}
        return self.nhdpid_flowline

    def map_waterbody_to_nhdpids(self):
        """
        Construct the waterbody_nhdpid and nhdpid_waterbody identifier mapping dictionaries.
        :return: None
        """
        self.waterbody_nhdpid = {r[0]: r[1]
                                 for r in arcpy.da.SearchCursor(self.waterbody, ['Permanent_Identifier', 'NHDPlusID'])}
        self.nhdpid_waterbody = {v: k for k, v in self.waterbody_nhdpid.items()}

    def drop_intermittent_flow(self):
        """
        Update the network to exclude intermittent flow from the tracing (consider segments disconnected if the flow
        between them is not permanent).
        :return: None
        """
        self.intermit_flowline_ids= {r[0] for r in arcpy.da.SearchCursor(self.flowline,
                                                        ['Permanent_Identifier', 'FCode']) if
                                     r[1] in [46003, 46007]}
        self.exclude_intermittent_flow = True

        # refresh the upstream/downstream dictionaries
        if self.upstream:
            self.prepare_upstream(force_refresh=True)
        if self.downstream:
            self.prepare_downstream(force_refresh=True)

    def include_intermittent_flow(self):
        """
        Update the network to include intermittent flow from the tracing (consider segments connected even if the flow
        between them is not permanent). Inclusion is the default, but this method can be used after
        drop_intermittent_flow was previously called.
        :return: None
        """
        self.intermit_flowline_ids = set()
        self.exclude_intermittent_flow = False

        # refresh the upstream/downstream dictionaries
        if self.upstream:
            self.prepare_upstream(force_refresh=True)
        if self.downstream:
            self.prepare_downstream(force_refresh=True)

    def map_flowlines_to_waterbodies(self):
        """
        Construct the flowline_waterbody identifier mapping dictionary.
        :return: self.flowline_waterbody
        """
        self.flowline_waterbody = {r[0]: r[1]
                                   for r in arcpy.da.SearchCursor(self.flowline,
                                                                  ['Permanent_Identifier',
                                                                   'WBArea_Permanent_Identifier'])
                                   if r[1]}
        return self.flowline_waterbody

    def map_waterbodies_to_flowlines(self):
        """
        Construct the waterbody_flowline identifier mapping dictionary.
        :return: self.waterbody_flowline
        """
        with arcpy.da.SearchCursor(self.flowline, ['Permanent_Identifier', 'WBArea_Permanent_Identifier']) as cursor:
            for row in cursor:
                flowline_id, waterbody_id = row
                if waterbody_id:
                    self.waterbody_flowline[waterbody_id].append(flowline_id)
        self.waterbody_flowline

    def define_lakes(self, strict_minsize=False, force_lagos=False):
        """Define the lakes to be used in NHDNetwork methods by creating an attribute with a dictionary of lakes and
        their areas.
        :param bool strict_minsize: If true, use 0.01 for lower area cutoff. LAGOS originally
        defined the base lake population using the USGS Albers area, so setting this to False
        allows slightly more lakes to be included in order to match that population 100%.
        :param bool force_lagos: Force the defined lakes to be limited to only those included in LAGOS. Generally not
        applicable/functional for users outside the LAGOS team, leave False. Consults lagos_pop_path for eligible lakes.
        :return self.lakes_areas: A dictionary with lake permids as the keys and the lake area as the values.
        """
        self.lakes_areas = {} # clear prior definition
        lagos_fcode_list = lagosGIS.LAGOS_FCODE_LIST
        lake_minsize = 0.01 if strict_minsize else 0.009
        if force_lagos and arcpy.Exists(self.lagos_pop_path):
            force_ids = {r[0] for r in arcpy.da.SearchCursor(self.lagos_pop_path, 'Permanent_Identifier')}
        else:
            force_ids = {}
        with arcpy.da.SearchCursor(self.waterbody, ['Permanent_Identifier', 'AreaSqKm', 'FCode']) as cursor:
            for row in cursor:
                id, area, fcode = row
                if (area >= lake_minsize and fcode in lagos_fcode_list) or id in force_ids:
                    self.lakes_areas[id] = area
        return self.lakes_areas

    # ---NETWORK SETUP FOR TRACING--------------------------------------------------------------------------------------
    def set_start_ids(self, waterbody_start_ids):
        """
        Activate network elements (waterbody and flowline) to be used as destinations for flow. Tracing proceeds
        upstream from these defined "start" locations.

        :param list waterbody_start_ids: List of WATERBODY Permanent_Identifiers to act as trace destinations (or tracing
        start locations).
        :return self.flowline_start_ids: List of FLOWLINE Permanent_Identifiers from which further tracing will start
        """
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        self.waterbody_start_ids = waterbody_start_ids
        flowline_ids_unflat = [self.waterbody_flowline[lake_id] for lake_id in waterbody_start_ids]
        # flatten before returning
        self.flowline_start_ids = [id for id_list in flowline_ids_unflat for id in id_list]
        return self.flowline_start_ids

    def set_stop_ids(self, waterbody_stop_ids):
        """
        Activate network elements (waterbody and flowline) to be used as barriers for upstream tracing.

        Flow cannot proceed through barriers, therefore the highest points in the traced network will be below the
        barrier elements.

        :param list waterbody_stop_ids: List of WATERBODY Permanent_Identifiers to act as barriers.
        :return self.flowline_stop_ids: List of FLOWLINE Permanent_Identifiers used as barriers
        """
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        self.waterbody_stop_ids = waterbody_stop_ids
        flowline_ids_unflat = [self.waterbody_flowline[lake_id] for lake_id in waterbody_stop_ids]
        # flatten before returning
        self.flowline_stop_ids = [id for id_list in flowline_ids_unflat for id in id_list]
        return self.flowline_stop_ids

    def activate_10ha_lake_stops(self):
        """Activate flow barriers at all lakes (as defined by LAGOS) greater than 10 hectares in size.
        :return self.tenha_waterbody_ids
        """
        self.waterbody_stop_ids = []
        if not self.lakes_areas:
            self.define_lakes()

        self.waterbody_stop_ids = [id for id, area in self.lakes_areas.items() if area >= 0.1]
        # and set the flowlines too
        self.set_stop_ids(self.waterbody_stop_ids)
        # and save stable for re-use by network class
        self.tenha_waterbody_ids = self.waterbody_stop_ids
        return self.tenha_waterbody_ids

    def deactivate_stops(self):
        """Deactivate all network barriers (flow proceeds unimpeded through entire network).
        :return None
        """
        self.waterbody_stop_ids = []
        self.flowline_stop_ids = []

    # ---WATERSHED TRACING METHODS--------------------------------------------------------------------------------------
    def trace_up_from_a_flowline(self, flowline_start_id, include_wb_permids=True):
        """
        Trace a network upstream of the input flowline and return the traced network identifiers in a list.
        Barriers currently activated on the network will be respected by the trace.
        A trace INCLUDES its own starting flowline.

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
        A trace INCLUDES its own starting flowline.

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

        lowest_flowline_start_ids = set(self.identify_lake_outlets(waterbody_start_id))

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
        Trace a network downstream of the input waterbody and return the traced network identifiers in a list.

        The highest flowline segments within the input waterbody will be identified and used to initiate the trace (in
        other words, traces will be found downstream of all waterbody inlets. Waterbodies with no flowline segments
        have an empty trace (are not in their own trace).

        Barriers currently activated on the network will be respected by the trace. The input waterbody will not
        act as a barrier for its own traced network.

        :param waterbody_start_id: Waterbody Permanent_Identifier of flow destination (downstream trace start point).
        :return: List of Permanent_Identifier values for flowlines and waterbodies in the downstream network trace,
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

        highest_flowline_start_ids = set(self.identify_lake_inlets(waterbody_start_id))

        # then trace down for all and flatten result
        unflat_trace_all = [self.trace_down_from_a_flowline(id, True) for id in highest_flowline_start_ids]
        all_to_ids = list({id for id_list in unflat_trace_all for id in id_list})

        # reset flowline_stop_ids
        if reset_stops:
            self.flowline_stop_ids = flowline_stop_ids_restore[:]
            self.waterbody_stop_ids = waterbody_stop_ids_restore[:]

        return all_to_ids

    def trace_up_from_waterbody_starts(self):
        """
        Batch trace up from all waterbody start locations currently set on the NHDNetwork instance.

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

    # KNOWN BUG 2020-09-24 njs: This function only adds back isolated lakes, not sink lakes that have no outflow.
    # This function should be modified to add those lakes.
    def trace_10ha_subnetworks(self, include_offnetwork=True):
        """
        Identify the upstream subnetworks of lakes > 10ha for each focal lake in the network's start population.
        :param include_offnetwork: Default True. Whether to exclude isolated/closed lakes (in or out of the focal lake's
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
        # key = waterbody identifier, value = trace of flowline & waterbody identifiers including key
        tenha_traces_no_stops = {k: set(v) for k, v in tenha_traces_no_stops_lists.items()}

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

            # will add ALL isolated/closed lakes back in, not just those in this region/full-trace
            if include_offnetwork:
                isolated_tenha = [k for k, v in tenha_traces_no_stops.items() if not v]
                if lake_id in isolated_tenha:
                    other_tenha_ids = [id for id in isolated_tenha if id != lake_id]
                else:
                    other_tenha_ids = isolated_tenha[:]
                subnetwork.extend(other_tenha_ids)
            subnetworks[lake_id] = subnetwork

        return subnetworks

    def define_tenha_sinks(self):
        """Defines the regions of the network where LAGOS treats flow as being "sunk" into the 10ha+ lake outlet.
        Regions must be off the main network (example: divergence leads to lake with no outlet and also to main river,
        the network upstream of this divergence will not be "sunk" into that lake)

        :return: dict Dictionary with key = Permanent_Identifier of isolated or closed 10ha+ lakes,
        value = upstream traces for the lake in the key
        """
        # save existing lakes definition and waterbody start ids for reset at end
        reset_starts = False
        if self.waterbody_start_ids:
            reset_starts = self.waterbody_start_ids

        # fetch tenha lake ids
        self.activate_10ha_lake_stops()
        self.deactivate_stops()

        # make list of ids for off-network 10ha+ lakes (Isolated, Closed, ClosedLk)
        off_classes = ['Isolated', 'Closed', 'ClosedLk']
        conn_class = {id:self.classify_waterbody_connectivity(id) for id in self.tenha_waterbody_ids}
        off_network_tenha = [id for id, c in conn_class.items() if c in off_classes]

        if off_network_tenha:
            self.set_start_ids(off_network_tenha)
            tenha_up = self.trace_up_from_waterbody_starts()
            on_network = set(self.trace_up_from_hu4_outlets())
            # drop any on-network traces from the results
            tenha_sink_traces = {k:list(set(v).difference(on_network)) for k, v in tenha_up.items()}

        else:
            tenha_sink_traces = {}

        # reset if needed
        if reset_starts:
            self.waterbody_start_ids = reset_starts

        return tenha_sink_traces

    def save_trace_catchments(self, trace, output_fc):
        """
        Select traced features from NHDFlowline and save to a new GIS (feature class) output.
        :param list trace: The result of one of the tracing methods in NHDNetwork.
        :param output_fc: A valid path to save a new feature class or shapefile.
        :return: Path to the output feature class
        """
        """"""
        query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                for id in trace]))
        output_fc = arcpy.Select_analysis(self.flowline, output_fc, query)
        return output_fc

    # ---INLET/OUTLET METHODS-------------------------------------------------------------------------------------------
    def trace_up_from_hu4_outlets(self):
        """
        Trace all of the main network, starting from the subregion outlets. The results can be used to identify
        whether network elements are on or off the main network.
        :return: List of all main network flowline Permanent_Identifiers
        """
        if not self.outlets:
            self.identify_subregion_outlets()
        results_unflat = [self.trace_up_from_a_flowline(id) for id in self.outlets]
        # convert list of trace-lists to one big list with unique elements
        results = [id for trace_list in results_unflat for id in trace_list]
        results_waterbodies = [self.flowline_waterbody[flowid]
                               for flowid in results if flowid in self.flowline_waterbody]
        results.extend(results_waterbodies)
        return results

    def identify_subregion_inlets(self):
        """Identify SUBREGION inlets: flowlines that flow in but have no upstream flowline in this gdb.
        :return self.inlets: A list of flowline Permanent_Identifiers for all of the inlets.
        """
        if not self.downstream:
            self.prepare_downstream()

        from_ids = set(self.downstream.keys()).difference({'0'})
        to_all = {f for to_list in self.downstream.values() for f in to_list}
        upstream_outlets = list(set(from_ids).difference(set(to_all)))
        inlets_unflat = [v for k, v in self.downstream.items() if k in upstream_outlets]
        inlets = [i for i_list in inlets_unflat for i in i_list]
        self.inlets = inlets
        return self.inlets

    def identify_subregion_outlets(self):
        """Identify SUBREGION outlets: flowlines that flow out but have no downstream flowline in this gdb.
        For subregions with frontal or closed drainage, the outlets for all subnetworks > 1/3 the total network size
        will be returned.
        :return self.outlets: A list of flowline Permanent_Identifiers for all of the outlets.
        """
        if not self.upstream:
            self.prepare_upstream()

        to_ids = set(self.upstream.keys()).difference({'0'})
        from_all = {f for from_list in self.upstream.values() for f in from_list}
        downstream_inlets = list(set(to_ids).difference(set(from_all)))
        outlets_unflat = [v for k, v in self.upstream.items() if k in downstream_inlets]
        outlets = [o for o_list in outlets_unflat for o in o_list]

        # for subregions with frontal or closed drainage, take the largest network's outlet
        # plus take any outlets with a network at least 1/2 the size of the main one in case there are multiple
        # or in other words, the largest sink possible by my design is 1/3 the hu4 size (by stream segment count)
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
        return self.outlets

    def identify_lake_outlets(self, waterbody_start_id):
        """
        Identify lake outlets: flowlines that flow out of the lake, that is, are the bottom-most flowlines in the
        lake's internal network of Artificial Path flowlines.
        :param str waterbody_start_id: The waterbody to identify outlets for.
        :return: A list of the flowline Permanent_Identifiers that are associated with the lake outlets
        """
        # set up the network if necessary
        if not self.upstream:
            self.prepare_upstream()
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        flowline_start_ids = set(self.waterbody_flowline[waterbody_start_id])  # one or more

        # identify the lowest start ids
        next_up = [self.upstream[id] for id in flowline_start_ids]
        next_up_flat = {id for id_list in next_up for id in id_list}
        lowest_flowline_start_ids = flowline_start_ids.difference(next_up_flat)  # lakes may have multiple outlets
        return list(lowest_flowline_start_ids)

    def identify_lake_inlets(self, waterbody_start_id):
        """
        Identify lake inlets: flowlines that flow in to the lake, that is, are the top-most flowlines in the
        lake's internal network of Artificial Path flowlines.
        :param str waterbody_start_id: The waterbody to identify inlets for.
        :return: A list of the flowline Permanent_Identifiers that are associated with the lake inlets
        """
        # set up the network if necessary
        if not self.downstream:
            self.prepare_downstream()
        if not self.waterbody_flowline:
            self.map_waterbodies_to_flowlines()
        flowline_start_ids = set(self.waterbody_flowline[waterbody_start_id])  # one or more

        # identify the highest start ids
        next_down = [self.downstream[id] for id in flowline_start_ids]
        next_down_flat = {id for id_list in next_down for id in id_list}
        highest_flowline_start_ids = flowline_start_ids.difference(next_down_flat)  # lakes may have multiple inlets
        return list(highest_flowline_start_ids)

    def identify_all_lakes_outlets(self):
        """Applies the identify_lake_outlets method to all (defined) lakes in the subregion and returns all outlets.
        :return: A list of all the flowline Permanent_Identifiers that are associated with ALL lake outlets
        """
        all_outlets = []
        if not self.lakes_areas:
            self.define_lakes()
        waterbody_start_ids = self.lakes_areas.keys()
        for waterbody_start_id in waterbody_start_ids:
            outlets = self.identify_lake_outlets(waterbody_start_id)
            all_outlets.extend(outlets)
        return all_outlets

    def identify_all_lakes_inlets(self):
        """Applies the identify_lake_inlets method to all (defined) lakes in the subregion and returns all inlets.
        :return: A list of all the flowline Permanent_Identifiers that are associated with ALL lake inlets
        """
        all_inlets = []
        if not self.lakes_areas:
            self.define_lakes()
        waterbody_start_ids = self.lakes_areas.keys()
        for waterbody_start_id in waterbody_start_ids:
            inlets = self.identify_lake_inlets(waterbody_start_id)
            all_inlets.extend(inlets)
        return all_inlets

    # ---OTHER CONNECTIVITY CALCULATIONS--------------------------------------------------------------------------------
    def classify_waterbody_connectivity(self, waterbody_start_id):
        """
        Classify the freshwater network connectivity associated with this waterbody. The four categories are defined as:
        Isolated--traces in both directions were empty (no network connectivity)
        Headwater--only the downstream trace contains network connectivity
        DrainageLk--traces either in both directions or only the upstream trace has network connectivity, and the
        upstream trace contains the identifier of one or more lakes over 10 hectares (as defined by the NHDNetwork
        class)
        Drainage--all lakes that do not meet one of the prior three criteria; traces either in both directions or only
        the upstream trace has network connectivity

        :param str waterbody_start_id: The Permanent_Identifier for the waterbody to be classified.
        :return: The connectivity class label, one of 'Isolated', 'Headwater', 'DrainageLk', 'Drainage.'
        """
        if not self.upstream:
            self.prepare_upstream()
        if not self.downstream:
            self.prepare_downstream()
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

            if len(nonself_trace_up) == 0: # no upstream connectivity
                if len(nonself_trace_down) > 0:
                    connclass = 'Headwater'
                if len(nonself_trace_down) == 0:
                    connclass = 'Isolated'

            else: # has upstream connectivity
                if len(nonself_trace_down) == 0: # no downstream connectivity
                    if tenha_upstream:
                        connclass = 'ClosedLk'
                    else:
                        connclass = 'Closed'
                else: # has downstream connectivity (and upstream)
                    if tenha_upstream:
                        connclass = 'DrainageLk'
                    else:
                        connclass = 'Drainage'

        return connclass

    def find_upstream_lakes(self, waterbody_start_id, result_type='list', area_threshold=0):
        """
        Identify and/or summarize the count or area of lakes upstream of this focal lake. The area_threshold value
         can be used to identify only upstream lakes above a certain size threshold (default is all lakes). Choose from
        returning a list of upstream lakes (result_type = 'list'), a count of upstream lakes ('count'), or the
        summarized area of the upstream lakes in hectares. ('area_hectares').
        :param str waterbody_start_id: The Permanent_Identifier for the lake to be assessed
        :param str result_type: 'list', 'count', or 'area_hectares'. The result type to be returned.
        :param float area_threshold: An area threshold applied to filter the upstream lakes to be identified/summarized.
        :return: A list, int, or float corresponding to the result_type selected.
        """
        valid_result_type = {'list', 'count', 'area_hectares'}
        if result_type not in valid_result_type:
            raise ValueError("result_type must be one of {}".format(valid_result_type))
        if not self.lakes_areas:
            self.define_lakes()

        countable_lakes = {id for id, area in self.lakes_areas.items() if area >= area_threshold}
        trace_up = set(self.trace_up_from_a_waterbody(waterbody_start_id)) # includes waterbody ids
        trace_up_other = trace_up.difference({waterbody_start_id})
        upstream_lakes = countable_lakes.intersection(trace_up_other)

        if result_type == 'list':
            return list(upstream_lakes)
        if result_type == 'count':
            lake_count = len(upstream_lakes)
            return lake_count
        if result_type == 'area_hectares':
            lake_area = sum([self.lakes_areas[id] for id in upstream_lakes]) * 100 # convert to hectares
            return lake_area