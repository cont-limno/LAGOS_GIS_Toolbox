import os
import re
from collections import defaultdict
from arcpy import management as DM
from arcpy import analysis as AN
import arcpy
import lagosGIS
import csiutils


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
    """Add NHDWaterbody features to the existing NHDPlusNHDPlusIDGridCode table and save the result as a new table.

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


def add_lake_seeds(nhdplus_catseed_raster, gridcode_table, eligible_lakes_fc, output_raster, nhdplus_waterbody_fc = ''):
    """
    Modify NHDPlus HR "catseed" raster to include lake-based pour points (seeds) for all lakes in need of watersheds.

    :param str nhdplus_catseed_raster: NHDPlus HR "catseed" TIFF raster for the HU4 needing watersheds created.
    :param str gridcode_table: NHDPlusID-GridCode mapping table (must contain lake seeds) that is the result of
    nhdplushr_tools.update_grid_codes()
    :param str eligible_lakes_fc: Lake feature class containing the lake polygons that will be used as pour points.
    :param str output_raster: Output pour points/seed raster for use in delineating watersheds.
    :param str nhdplus_waterbody_fc: (Optional) If NHDPlusID is not already included in eligible_lakes_fc, specify
    an NHDPlus HR NHDWaterbody feature class to transfer NHDPlusID from
    :return: ArcGIS Result object for output_raster
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
    eligible_lakes_copy = AN.Select(eligible_lakes_fc, 'eliglible_lakes_copy', filter_clause)
    DM.AddField(eligible_lakes_copy, 'GridCode', 'LONG')
    with arcpy.da.UpdateCursor(eligible_lakes_copy, ['NHDPlusID', 'GridCode']) as u_cursor:
        for row in u_cursor:
            new_row = (row[0], nhdpid_grid[row[0]])
            u_cursor.updateRow(new_row)

    # convert lakes
    lake_seeds = arcpy.PolygonToRaster_conversion(eligible_lakes_copy, 'GridCode', 'lake_seeds')
    output_dir = os.path.dirname(output_raster)
    output_base = os.path.basename(output_raster)
    combined_seeds = DM.MosaicToNewRaster([nhdplus_catseed_raster, lake_seeds], output_dir, output_base,
                         pixel_type='32_BIT_UNSIGNED', number_of_bands='1', mosaic_method='LAST')
    return combined_seeds


def lagos_watershed(flowdir_raster, catseed_raster, gridcode_table, output_fc):
    """
    Delineate watersheds and label them with GridCode, NHDPlusID, SourceFC, and VPUID for the water feature.
    :param flowdir_raster: NHDPlus HR "fdr" TIFF raster for the HU4 needing watersheds delineated.
    :param catseed_raster: Pour points raster, the result of nhdplustools_hr.add_lake_seeds()
    :param gridcode_table: Modified NHDPlusID-GridCode mapping table, the result of nhdplustools_hr.update_grid_codes()
    :param output_fc: Output feature class for the watersheds
    :return: ArcGIS Result object for output_fc
    """
    # establish environments
    arcpy.CheckOutExtension('Spatial')
    arcpy.env.workspace = 'in_memory'
    arcpy.env.parallelProcessingFactor = '75%'

    # delineate watersheds with ArcGIS Watershed tool, then convert to one polygon per watershed
    arcpy.AddMessage("Delineating watersheds...")
    sheds = arcpy.sa.Watershed(flowdir_raster, catseed_raster, 'Value')
    arcpy.AddMessage("Watersheds complete.")
    sheds_poly = arcpy.RasterToPolygon_conversion(sheds, 'sheds_poly', 'NO_SIMPLIFY', 'Value')
    DM.AlterField(sheds_poly, 'gridcode', 'GridCode', clear_field_alias=True)
    output_fc = DM.Dissolve(sheds_poly, output_fc, 'GridCode')

    # "Join" to the other identifiers via GridCode
    gridcode_dict = {r[0]:r[1:] for r in arcpy.da.SearchCursor(gridcode_table,
                                                                 ['GridCode', 'NHDPlusID', 'SourceFC', 'VPUID'])}
    DM.AddField(output_fc, 'NHDPlusID', 'DOUBLE')
    DM.AddField(output_fc, 'SourceFC', 'TEXT', field_length=20)
    DM.AddField(output_fc, 'VPUID', 'TEXT', field_length=8)
    with arcpy.da.UpdateCursor(output_fc, ['GridCode', 'NHDPlusID', 'SourceFC', 'VPUID']) as u_cursor:
        for row in u_cursor:
            new_row = (row[0],) + gridcode_dict[row[0]]
            u_cursor.updateRow(new_row)

     # TODO: Add Permanent_Identifier and lagoslakeid so that we can publish these, as-is

    return output_fc


class NHDNetwork:
    def __init__(self, nhdplus_gdb, plus=True):
        self.gdb = nhdplus_gdb
        self.plus = plus
        if self.plus:
            self.from_column = 'FromPermID'
            self.to_column = 'ToPermID'
            self.flow = os.path.join(nhdplus_gdb, 'NHDPlusFlow')
        else:
            self.from_column = 'From_Permanent_Identifier'
            self.to_column = 'To_Permanent_Identifier'
            self.flow = os.path.join(nhdplus_gdb, 'NHDFlow')
            self.catchment = os.path.join(nhdplus_gdb, 'NHDPlusCatchment')
            self.sink = os.path.join(nhdplus_gdb, 'NHDPlusSink')
        self.waterbody = os.path.join(nhdplus_gdb, 'NHDWaterbody')
        self.flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
        self.waterbody_start_ids = []
        self.flowline_start_ids = []
        self.flowline_stop_ids = []
        self.waterbody_stop_ids = []
        self.upstream = defaultdict(list)
        self.nhdpid_flowline = defaultdict(list)
        self.flowline_waterbody = defaultdict(list)
        self.waterbody_flowline = defaultdict(list)
        self.waterbody_nhdpid = defaultdict(list)
        self.nhdpid_waterbody = defaultdict(list)


    def prepare_upstream(self):
        """Read the file GDB flow table and collapse into a flow dictionary."""
        with arcpy.da.SearchCursor(self.flow, [self.from_column, self.to_column]) as cursor:
            for row in cursor:
                from_id, to_id = row
                if from_id == '0':
                    self.upstream[to_id] = []
                else:
                    self.upstream[to_id].append(from_id)

    def map_nhdpid_to_flowlines(self):
        self.nhdpid_flowline = {r[0]:r[1]
                         for r in arcpy.da.SearchCursor(self.flowline, ['NHDPlusID', 'Permanent_Identifier'])}

    def map_waterbody_to_nhdpids(self):
        self.waterbody_nhdpid = {r[0]:r[1]
                         for r in arcpy.da.SearchCursor(self.waterbody, ['Permanent_Identifier', 'NHDPlusID'])}
        self.nhdpid_waterbody = {v:k for k, v in self.waterbody_nhdpid.items()}

    def map_flowlines_to_waterbodies(self):
        self.flowline_waterbody = {r[0]:r[1]
                                   for r in arcpy.da.SearchCursor(self.flowline,
                                                             ['Permanent_Identifier', 'WBArea_Permanent_Identifier'])
                                                             if r[1]}

    def map_waterbodies_to_flowlines(self):
        with arcpy.da.SearchCursor(self.flowline, ['Permanent_Identifier', 'WBArea_Permanent_Identifier']) as cursor:
            for row in cursor:
                flowline_id, waterbody_id = row
                if waterbody_id:
                    self.waterbody_flowline[waterbody_id].append(flowline_id)

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

    def deactivate_stops(self):
        self.waterbody_stop_ids = []
        self.flowline_stop_ids = []

    def trace_up_from_a_flowline(self, flowline_start_id, include_wb_permids = True):
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
            wb_permids_set = {self.flowline_waterbody[id] for id in all_from_ids if id in self.flowline_waterbody}
            wb_permids = list(wb_permids_set.difference(set(self.waterbody_stop_ids))) # if stops present, remove
            all_from_ids.extend(wb_permids)
        return all_from_ids

    def trace_up_from_a_waterbody(self, waterbody_start_id, include_wb_permids = True):
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

        # then trace up for all
        unflat_trace_all = [self.trace_up_from_a_flowline(id, include_wb_permids) for id in lowest_flowline_start_ids]
        all_from_ids = list({id for id_list in unflat_trace_all for id in id_list})

        # reset flowline_stop_ids
        if reset_stops:
            self.flowline_stop_ids = flowline_stop_ids_restore[:]
            self.waterbody_stop_ids = waterbody_stop_ids_restore[:]

        return all_from_ids

    def trace_up_from_waterbody_starts(self):
        if self.waterbody_start_ids:
            results = {id: self.trace_up_from_a_waterbody(id) for id in self.waterbody_start_ids}
            return results
        else:
            raise Exception("Populate start IDs with set_start_ids before calling trace_up_from_starts().")


def aggregate_watersheds(watersheds_fc, nhdplus_gdb, eligible_lakes_fc, output_fc,
                         mode = ['interlake', 'network', 'self']):
    """Creates a feature class with all the aggregated upstream watersheds for all
    eligible lakes in this subregion."""
    arcpy.env.workspace = 'in_memory'
    temp_gdb = csiutils.create_temp_GDB('aggregate_watersheds')

    # get this huc4
    huc4_code = re.search('\d{4}', os.path.basename(nhdplus_gdb)).group()
    wbd_hu4 = os.path.join(nhdplus_gdb, "WBDHU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause4 = """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhdplus_gdb, field_name), huc4_code)
    hu4 = arcpy.Select_analysis(wbd_hu4, "hu4", whereClause4)

    # initialize the network object and built a dictionary we'll use
    nhd_network = NHDNetwork(nhdplus_gdb)

    # make layers for upcoming spatial selections
    # and fcs in memory
    waterbody_lyr = DM.MakeFeatureLayer(nhd_network.waterbody)

    # have to send watersheds to a temp gdb so we can use an index
    if not nhd_network.nhdpid_flowline:
        nhd_network.map_nhdpid_to_flowlines()
    if not nhd_network.nhdpid_waterbody:
        nhd_network.map_waterbody_to_nhdpids()
    watersheds_fc_copy = DM.CopyFeatures(watersheds_fc, 'watersheds_fc_copy')
    DM.AddField(watersheds_fc_copy, 'Permanent_Identifier', 'TEXT', field_length = 40)
    with arcpy.da.UpdateCursor(watersheds_fc_copy, ['NHDPlusID', 'Permanent_Identifier']) as u_cursor:
        for row in u_cursor:
            nhdpid, permid = row
            if nhdpid in nhd_network.nhdpid_flowline:
                permid = nhd_network.nhdpid_flowline[nhdpid]
            elif nhdpid in nhd_network.nhdpid_waterbody:
                permid = nhd_network.nhdpid_waterbody[nhdpid]
            else:
                permid = None # sinks, no permanent identifiers, can't be traced, which is fine.
            u_cursor.updateRow((nhdpid, permid))

    # dropping extra watersheds fields speeds up dissolve 6X, which we NEED
    temp_gdb_watersheds_path = os.path.join(temp_gdb, 'watersheds_simple')
    watersheds_simple = lagosGIS.select_fields(watersheds_fc_copy, temp_gdb_watersheds_path, ['Permanent_Identifier'])
    DM.AddIndex(watersheds_simple, 'Permanent_Identifier', 'permid_idx')
    watersheds_lyr = DM.MakeFeatureLayer(watersheds_simple, 'watersheds_lyr')

    # intersect eligible_lakes and lakes for this NHD gdb (eligible_lakes can have much larger spatial extent)
    # any lake id that doesn't intersect/inner join will be DROPPED and will not get a watershed traced
    gdb_wb_permids = {row[0] for row in arcpy.da.SearchCursor(nhd_network.waterbody, 'Permanent_Identifier') if row[0]}
    eligible_lake_ids = {row[0] for row in arcpy.da.SearchCursor(eligible_lakes_fc, 'Permanent_Identifier')}
    matching_ids = list(gdb_wb_permids.intersection(eligible_lake_ids))



    # configure the network and make 10-ha lake catchment layer, if needed
    if mode == 'interlake':
        nhd_network.activate_10ha_lake_stops() # get the stop ids
        tenha_start_ids = nhd_network.waterbody_stop_ids
        print "tenha start ids length: {}".format(len(tenha_start_ids))
        nhd_network.set_start_ids(tenha_start_ids)
        nhd_network.deactivate_stops()
        tenha_traces_no_stops = nhd_network.trace_up_from_waterbody_starts() # with no stops!
        nhd_network.set_start_ids(matching_ids)
        traces_no_stops = nhd_network.trace_up_from_waterbody_starts()
        nhd_network.activate_10ha_lake_stops()


    # run the traces. trace[id] = list of all flowline IDS in trace
    nhd_network.set_start_ids(matching_ids)
    traces = nhd_network.trace_up_from_waterbody_starts()

    if mode == 'interlake':
        minus_traces = dict()
        for k, v in traces_no_stops.items():
            this_lake_id = k
            full_network = set(v) # still missing sinks
            # determine if this lake is upstream of any
            reset_kv = []
            if k in tenha_traces_no_stops:
                reset_kv = tenha_traces_no_stops[k]
                del tenha_traces_no_stops[k] # take this lake's network out temporarily
            # if this lake id in the trace, then the dict entry is for a downstream lake. keep only upstream.
            upstream_tenha_subnets = [v1 for k1, v1 in tenha_traces_no_stops.items() if this_lake_id not in v1]
            upstream_subnet_ids = {id for id_list in upstream_tenha_subnets for id in id_list}
            if reset_kv:
                tenha_traces_no_stops[k] = reset_kv # restore this lake's network to the dict
            minus_traces[k] = full_network.intersection(upstream_subnet_ids)

    arcpy.AddMessage("Network ready for tracing.")

    counter = 0
    sink_lake_ids = []
    # The specific recipe for speed in this loop (about 0.8 seconds per loop/drainage lake):
    # 1) The watersheds dataset being queried must have an index. (use temp_gdb instead of in_memory above)
    # 2) It is faster to AN.Select from a feature layer of the indexed lake/watershed dataset than the dataset itself.
    # 3) Dissolve must work on something in_memory (not a selected layer on disk) for a big speed increase.
    # 4) Extraneous fields are NOT ignored by Dissolve and slow it down, so they are removed earlier.
    # 5) Spatial queries were actually quite fast but picked up extraneous catchments, so we will not use that method.
    # 6) Deletions in the loop waste time (1/3 second per loop) and overwriting causes no problems.
    # 7) Avoid processing
    arcpy.env.overwriteOutput = True
    for lake_id in matching_ids:
        # TODO: Remove
        print(lake_id)
        counter +=1
        if counter > 200:
            break
        this_lake = AN.Select(waterbody_lyr, 'this_lake', "Permanent_Identifier = '{}'".format(lake_id))
        trace_permids = traces[lake_id]
        if trace_permids: # if lake on network
            # select flowlines matching trace, and then watersheds intersecting flowlines
            flowline_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                             for id in trace_permids]))
            # select the watersheds by ID because too much spatial mismatch along boundaries
            selected_watersheds = AN.Select(watersheds_lyr, 'selected_watersheds', flowline_query)

            # dissolve if many
            if len(trace_permids) > 1:
                this_watershed_holes = DM.Dissolve(selected_watersheds, 'this_watershed_holes')  # sheds has selection
                DM.AddField(this_watershed_holes, 'Permanent_Identifier', 'TEXT', field_length=40)
                DM.CalculateField(this_watershed_holes, 'Permanent_Identifier', """'{}'""".format(lake_id), "PYTHON")
                no_holes = DM.EliminatePolygonPart(this_watershed_holes,
                                                   'no_holes', 'PERCENT', part_area_percent = '99.999')

                if mode == 'interlake':
                    if minus_traces[lake_id]:
                        #select matching watersheds
                        tenha_subnetworks_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                         for id in minus_traces[lake_id]]))
                        other_tenha = AN.Select(watersheds_lyr, 'other_tenha', tenha_subnetworks_query)
                        # since subnetworks can be hole-y due to sinks also, need to dissolve before erasing
                        other_tenha_dissolved = DM.Dissolve(other_tenha, 'other_tenha_dissolved')
                        this_watershed = arcpy.Erase_analysis(no_holes, other_tenha_dissolved, 'this_watershed')
                    # if nothing in minus_traces, there were no 10ha lakes upstream, so nothing to erase
                    else:
                        this_watershed = no_holes
                else:
                    this_watershed = no_holes

            # otherwise we already have only one shed in correct format already
            else:
                this_watershed = selected_watersheds

            # erase lake from its own shed AFTER aggregation
            lakeless_watershed = arcpy.Erase_analysis(this_watershed, this_lake,
                                                      'lakeless_watershed')

            # write out
            if not arcpy.Exists('merged_fc'):
                merged_fc = DM.CopyFeatures(lakeless_watershed, 'merged_fc')
                # to avoid append mismatch due to permanent_identifier
                DM.AlterField(merged_fc, 'Permanent_Identifier', field_length=40)
            else:
                print(DM.GetCount(merged_fc).getOutput(0))
                DM.Append(lakeless_watershed, merged_fc, 'NO_TEST')

        else: # lake is has a "sink" catchment
            sink_lake_ids.append(lake_id)
    arcpy.env.overwriteOutput = False

    # handle all the sink lakes at once
    if not nhd_network.waterbody_nhdpid:
        nhd_network.map_waterbody_to_nhdpids()
    sink_nhdpids = [nhd_network.waterbody_nhdpid[id] for id in sink_lake_ids]
    waterbodies_query = 'NHDPlusID IN ({})'.format(','.join(['{:14.0f}'.format(id)
                                                                             for id in sink_nhdpids]))
    these_lakes = AN.Select(nhd_network.waterbody, 'these_lakes', waterbodies_query)
    watersheds_query = '{} IN ({})'.format('NHDPlusID', ','.join(['{:14.0f}'.format(id)
                                                                        for id in sink_nhdpids]))

    # use original watersheds here, not the geom layer which has no fields
    these_watersheds = AN.Select(watersheds_fc_copy, 'these_watersheds', watersheds_query)
    print(DM.GetCount(these_watersheds).getOutput(0))
    lakeless_watersheds = AN.Erase(these_watersheds, these_lakes, 'lakeless_watersheds')
    print(DM.GetCount(merged_fc).getOutput(0))
    print(DM.GetCount(lakeless_watersheds).getOutput(0))
    DM.Append(lakeless_watersheds, merged_fc, 'NO_TEST')

    # add the flag for network watershed == interlake watershed
    if mode == 'interlake':
        DM.AddField(merged_fc, 'equals_network_watershed', 'TEXT', field_length=1)
        with arcpy.da.UpdateCursor(merged_fc, ['equals_network_watershed', 'Permanent_Identifier']) as u_cursor:
            for row in u_cursor:
                # lookup the value we calculated earlier
                if minus_traces[row[1]]:
                    row[0] = 'N'
                else:
                    row[0] = 'Y'
                u_cursor.updateRow(row)

    DM.DeleteField(merged_fc, 'ORIG_FID')
    output_fc = arcpy.Clip_analysis(merged_fc, hu4, output_fc)
    for item in [hu4, merged_fc, watersheds_simple]:
        DM.Delete(item)
    DM.Delete(temp_gdb)

    return output_fc