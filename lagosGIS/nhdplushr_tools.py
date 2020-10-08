import os
from collections import defaultdict
from arcpy import management as DM
from arcpy import analysis as AN
import arcpy
import lagosGIS
from NHDNetwork import NHDNetwork


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

    Only lakes over 0.009 sq. km. in area that match the LAGOS lake filter will be added. The features added will be
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








