# filename: nhd_plus_watersheds_tools.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)--tools called in individual scripts to make tools

import os
import datetime as dt
import subprocess as sp
from collections import defaultdict
from arcpy import management as DM
from arcpy import analysis as AN
import arcpy
import lagosGIS
from lagosGIS.NHDNetwork import NHDNetwork

__all__ = [
    "add_waterbody_nhdpid",
    "update_grid_codes",
    "add_lake_seeds",
    "revise_hydrodem",
    "flow_direction",
    "delineate_catchments"
]

def add_waterbody_nhdpid(nhdplus_waterbody_fc, eligible_lakes_fc):
    """
    Transfer waterbody NHDPlusID values from NHDPlus HR geodatabase to another lake/waterbody feature class.

    :param nhdplus_waterbody_fc: NHDWaterbody feature class from an NHDPlus HR geodatabase, containing IDs to transfer
    :param eligible_lakes_fc: A lake/waterbody dataset you want to modify by transferring NHDPlusIDs to a new field.
    :return: ArcGIS Result object for eligible_lakes_fc

    """
    arcpy.AddMessage("Finding ids...")
    # add field first time
    if not arcpy.ListFields(eligible_lakes_fc, 'NHDPlusID'):
        DM.AddField(eligible_lakes_fc, 'NHDPlusID', 'DOUBLE')

    # get nhdpids
    wbplus_permid_nhdpid = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhdplus_waterbody_fc,
                                                                      ['Permanent_Identifier', 'NHDPlusID'])}
    arcpy.AddMessage("Transferring ids...")
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


def add_lake_seeds(nhdplus_catseed_raster, nhdplus_gdb, gridcode_table, eligible_lakes_fc, output_raster):
    """
    Modify NHDPlus catseed raster to
    1) include all LAGOS lakes as pour points,
    2) remove pour points associated with
     artificial path flowlines going through those lakes (most are covered automatically but some narrow lakes are
     a problem that needs specific handling),
    3) remove any waterbodies <1ha that were erroneously permitted as sinks in NHDPlus (those with "NHDWaterbody closed
    lake" as the Purpose code.

    :param str nhdplus_catseed_raster: NHDPlus HR catseed raster used to set snap raster, can also use subregion DEM
    :param str nhdplus_gdb: NHDPlus HR geodatabase for the HU4 needing watersheds created.
    :param str gridcode_table: NHDPlusID-GridCode mapping table (must contain lake seeds) that is the result of
    nhdplushr_tools.update_grid_codes()
    :param str eligible_lakes_fc: Lake feature class containing the lake polygons that will be used as pour points.
    :param str output_raster: Output pour points/seed raster for use in delineating watersheds.
    :return: Path for output_raster

    """
    # not much of a test, if the field exists but isn't populated, this tool will run with no IDs populated
    if not arcpy.ListFields(eligible_lakes_fc, 'NHDPlusID'):
        try:
            add_waterbody_nhdpid(os.path.join(nhdplus_gdb, 'NHDWaterbody'), eligible_lakes_fc)
        except:
            raise Exception('''
        No NHDPlusID field found in eligible_lakes_fc. Please supply optional nhdplus_waterbody_fc argument using
        the NHDWaterbody feature class for the NHDPlus-HR HUC4 you are trying to process.''')

    arcpy.env.workspace = 'in_memory'
    arcpy.env.scratchWorkspace = os.path.dirname(output_raster)
    # essential environment settings for conversion to raster
    arcpy.env.snapRaster = nhdplus_catseed_raster
    arcpy.env.extent = nhdplus_catseed_raster
    arcpy.env.cellSize = nhdplus_catseed_raster
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(5070)
    pour_dir = os.path.dirname(output_raster)

    # --- WATERBODY SEEDS PREP ------------------
    # add gridcodes to lakes
    nhdpid_grid = {r[0]: r[1] for r in arcpy.da.SearchCursor(gridcode_table, ['NHDPlusID', 'GridCode'])}
    this_gdb_ids = tuple(nhdpid_grid.keys())
    filter_clause = 'NHDPlusID IN {}'.format(this_gdb_ids)
    eligible_lakes_copy = AN.Select(eligible_lakes_fc, 'eligible_lakes_copy', filter_clause)
    DM.AddField(eligible_lakes_copy, 'GridCode', 'LONG')
    with arcpy.da.UpdateCursor(eligible_lakes_copy, ['NHDPlusID', 'GridCode']) as u_cursor:
        for row in u_cursor:
            new_row = (row[0], nhdpid_grid[row[0]])
            u_cursor.updateRow(new_row)

    # --- VECTOR TO RASTER ------------------------
    # these must be saved as tifs for the mosiac nodata values to work with the watersheds tool
    lake_seeds = os.path.join(pour_dir, "lakes_raster.tif")
    arcpy.PolygonToRaster_conversion(eligible_lakes_copy, "GridCode", lake_seeds, "", "", 10)
    combined = DM.MosaicToNewRaster([nhdplus_catseed_raster, lake_seeds], arcpy.env.workspace, 'combined',
                                    pixel_type='32_BIT_SIGNED', number_of_bands='1', mosaic_method='LAST')
    DM.BuildRasterAttributeTable(combined)

    # --- MODIFY TO DROP ERROR SINK AND DANGLING FLOWLINES THROUGH LAKES

    # IDENTIFY POTENTIAL DANGLING FLOWLINES
    # Get gridcodes for Artificial Paths associated with lakes
    def find_lakepath_gridcodes():
        waterbody = os.path.join(nhdplus_gdb, 'NHDWaterbody')
        flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
        lake_xwalk = {r[0]:r[1] for r in arcpy.da.SearchCursor(waterbody, ['NHDPlusID', 'Permanent_Identifier'])}
        flowline_xwalk = {r[0]:r[1]
                          for r in arcpy.da.SearchCursor(flowline, ['WBArea_Permanent_Identifier', 'NHDPlusID'])
                          if r[0]}
        result = filter(lambda x: x is not None, [nhdpid_grid.get(
            flowline_xwalk.get(
                lake_xwalk.get(id))) for id in this_gdb_ids]
        )
        return result
    lakepath_gridcodes = find_lakepath_gridcodes()

    # IDENTIFY ERRONEOUS SINKS
    # due to burn/catseed errors in NHD, we are removing all sinks marked "NHDWaterbody closed lake" (SC)
    # remove from existing raster so we don't have to duplicate their flowline processing steps
    # in regions with no error: no change, correctly indicated closed lakes would be removed but we have overwritten
    # them with our own lake poly seeds anyway.
    sink = os.path.join(nhdplus_gdb, 'NHDPlusSink')
    sinks_to_remove = [r[0] for r in arcpy.da.SearchCursor(sink, ['GridCode'], "PurpCode = 'SC'")]

    # Merge flowpaths and sinks; test for whether we need to run cleaning step
    undesirable_codes = lakepath_gridcodes + sinks_to_remove
    gridcodes_in_raster = set([r[0] for r in arcpy.da.SearchCursor(combined, 'VALUE')])
    removable_codes = gridcodes_in_raster.intersection(undesirable_codes)

    if removable_codes:
        arcpy.AddMessage("Modifying catseed raster to clean lake seeds...")
        arcpy.CheckOutExtension('Spatial')
        cleaned = arcpy.sa.SetNull(combined, combined, 'VALUE in ({})'.format(','.join(['{}'.format(id)
                                                                                           for id in removable_codes])))
        cleaned.save(output_raster)
        arcpy.CheckInExtension('Spatial')

    return output_raster


def revise_hydrodem(nhdplus_gdb, hydrodem_raster, filldepth_raster, lagos_catseed_raster, out_raster):
    """Uses the NHDPlus hydrodem and filldepth to reconstitute the un-filled burned DEM, and then synchronizes
    the protected lake regions (those with NoData in center to prevent filling in TauDEM Pit Remove) with the
    catseed raster as modified in add_lake_seeds.

    :param nhdplus_gdb: The geodatabase for the subregion getting the DEM updated
    :param hydrodem_raster: The hydro-conditioned DEM to be updated
    :param filldepth_raster: The fill depth raster provided by NHD Plus
    :param lagos_catseed_raster: The modified "catseed" raster created with the Add Lake Seeds tool
    :param out_raster: The output raster
    :return:
    """

    # per suggestion by Price here
    # https://community.esri.com/people/curtvprice/blog/2017/03/03/temporary-rasters-in-arcpy
    arcpy.env.scratchWorkspace = os.path.dirname(lagos_catseed_raster)
    arcpy.env.workspace = arcpy.env.scratchWorkspace
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = filldepth_raster
    projection = arcpy.SpatialReference(5070)
    arcpy.env.outputCoordinateSystem = projection
    arcpy.CheckOutExtension('Spatial')

    # get back to the burned DEM before filling
    filldepth_raster = arcpy.sa.Raster(filldepth_raster)
    filldepth = arcpy.sa.Con(arcpy.sa.IsNull(filldepth_raster), 0, filldepth_raster)

    burned_dem = arcpy.sa.Raster(hydrodem_raster) - filldepth

    arcpy.env.workspace = 'in_memory'
    # identify valid sinks
    network = NHDNetwork(nhdplus_gdb)
    waterbody_ids = network.define_lakes(strict_minsize=False, force_lagos=True).keys()
    arcpy.AddMessage("Identifying sink lakes...")
    lake_conn_classes = {id:network.classify_waterbody_connectivity(id) for id in waterbody_ids}
    sink_lake_ids = [k for k,v in lake_conn_classes.items() if v in ('Isolated', 'TerminalLk', 'Terminal')]
    sink_lakes_query = 'Permanent_Identifier IN ({})'.format(
        ','.join(['\'{}\''.format(id) for id in sink_lake_ids]))
    sink_lakes = arcpy.Select_analysis(network.waterbody, 'sink_lakes', sink_lakes_query)

    # protect these sink lakes in DEM
    sink_centroids = arcpy.FeatureToPoint_management(sink_lakes, 'sink_centroids', 'INSIDE')
    sinks_raster0 = arcpy.PolygonToRaster_conversion(sink_lakes, "OBJECTID", "sinks_raster0", cellsize=10)
    centroids_raster0 = arcpy.PointToRaster_conversion(sink_centroids, "OBJECTID", "centroids_raster0", cellsize=10)
    sinks = arcpy.sa.Raster(sinks_raster0) > 0
    centroids = arcpy.sa.Raster(centroids_raster0) > 0
    sinks_raster = arcpy.sa.Con(arcpy.sa.IsNull(sinks), 0, sinks)
    centroids_raster = arcpy.sa.Con(arcpy.sa.IsNull(centroids), 0, centroids)


    # burn in the sink lakes and add the nodata protection in the center
    arcpy.AddMessage("Burning sinks...")
    areal_drop = 10000 # in cm, so 100m elevation drop
    burnt = burned_dem - (areal_drop * sinks_raster)
    protected = arcpy.sa.SetNull(centroids_raster == 1, burnt)

    # remove all fill-protected lakes that are NOT also in our modified pour points--these are the erroneous sinks
    # use raster calculator to fill nodata with min value that surrounds it (lake is flattish)
    dem_null = arcpy.sa.IsNull(protected)
    lagos_null = arcpy.sa.IsNull(lagos_catseed_raster)
    replacement = arcpy.sa.FocalStatistics(protected, statistics_type='MINIMUM')  # assign lake elevation value
    result = arcpy.sa.Con((dem_null == 1) & (lagos_null == 1), replacement, protected)

    # save the final result
    result.save(out_raster)

    # cleanup
    arcpy.CheckInExtension('Spatial')
    arcpy.env.overwriteOutput = False

def make_hydrodem(burned_raster, hydrodem_raster_out):
    """
    Remove pits from hydro-enforced raster and fill using TauDEM tools.
    :param burned_raster: Output of Burn Streams or Fix HydroDEM
    :param hydrodem_raster_out: The final "hydrodem" raster output to save
    :return:
    """
    arcpy.AddMessage('Filling DEM started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    pitremove_cmd = 'mpiexec -n 8 pitremove -z {} -fel {}'.format(burned_raster, hydrodem_raster_out)
    print(pitremove_cmd)
    try:
        sp.call(pitremove_cmd, stdout=sp.PIPE, stderr=sp.STDOUT)
    except:
        arcpy.AddMessage("Tool did not run. Check for correct installation of TauDEM tools.")

def flow_direction(hydrodem_raster, flow_direction_raster_out):
    """
    Create the flow direction raster for the subregion.
    :param hydrodem_raster: The modified or final hydrodem raster
    :param flow_direction_raster_out: The output raster containing the flow directions
    :return:
    """
    arcpy.CheckOutExtension('Spatial')
    arcpy.AddMessage('Flow direction started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    flow_dir = arcpy.sa.FlowDirection(hydrodem_raster)
    # enforce same bounds as NHD fdr, so catchments have same HU4 boundary
    # TODO: For non-hr, clip to HU4 instead
    print(arcpy.Describe(flow_dir).spatialReference.name)
    print(arcpy.Describe(hydrodem_raster).spatialReference.name)
    print(arcpy.Describe(flow_dir).extent)
    print(arcpy.Describe(hydrodem_raster).extent)
    flow_dir_clipped = arcpy.sa.Con(arcpy.sa.IsNull(hydrodem_raster), hydrodem_raster, flow_dir)
    flow_dir_clipped.save(flow_direction_raster_out)
    arcpy.CheckInExtension('Spatial')

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
    arcpy.AddMessage("Delineating catchments...")
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

    # calculate whether the watershed is on the main network
    on_network = set(nhd_network.trace_up_from_hu4_outlets())

    # update table with ids and flags
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

    def reassign_slivers_to_lakes(catchments_fc):
        # remove slight overlaps with neighboring lakes that are in the LAGOS population
        waterbody_ids = nhd_network.define_lakes(strict_minsize=False, force_lagos=True).keys()
        waterbody_query = 'Permanent_Identifier IN ({})'.format(
            ','.join(['\'{}\''.format(id) for id in waterbody_ids]))
        waterbody = arcpy.Select_analysis(nhd_network.waterbody, 'waterbody', waterbody_query)
        waterbody_only = lagosGIS.select_fields(waterbody, 'waterbody_only', ['Permanent_Identifier'], convert_to_table=False)
        union = arcpy.Union_analysis([dissolved, waterbody_only], 'union')

        # move slivers in union into the lake watershed as long as they intersect the lake
        with arcpy.da.UpdateCursor(union, ['Permanent_Identifier', 'Permanent_Identifier_1']) as cursor:
            for row in cursor:
                if row[1] != '': # union produces blank strings instead of nulls
                    row[0] = row[1] # if lake_id, then use it as the catchment id (move slivers into lake catchment)
                cursor.updateRow(row)

        arcpy.DeleteField_management(union, 'Permanent_Identifier_1')
        arcpy.DeleteField_management(union, 'FID_1')
        reassigned = arcpy.Dissolve_management(union, 'reassigned', 'Permanent_Identifier')
        return reassigned

    reassigned_output = reassign_slivers_to_lakes(dissolved)
    arcpy.CopyFeatures_management(reassigned_output, output_fc)

    return output_fc


# #---FUNCTIONS THAT DIDN'T END UP BEING USED---------------------------------------------------------------------------
# def assign_catchments_to_lakes(nhdplus_gdb, output_fc):
#     """Use the """
#     # paths
#     nhd_cat = os.path.join(nhdplus_gdb, 'NHDPlusCatchment')
#     nhd_flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
#     nhd_wb = os.path.join(nhdplus_gdb, 'NHDWaterbody')
#
#     # copy to output and prep
#     nhd_cat_copy = DM.CopyFeatures(nhd_cat, output_fc)
#     DM.AddField(nhd_cat_copy, 'Lake_PermID', field_type='TEXT', field_length=40)
#     DM.AddField(nhd_cat_copy, 'Flowline_PermID', field_type='TEXT', field_length=40)
#
#     # build dictionaries for the joins
#     nhd_flowline_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
#                                                                    ['NHDPlusID', 'Permanent_Identifier'])}
#     nhd_wbarea_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
#                                                                  ['NHDPlusID', 'WBArea_Permanent_Identifier'])}
#     nhd_wb_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_wb, ['NHDPlusID', 'Permanent_Identifier'])}
#     valid_wb_ids = set(nhd_wb_dict.values())
#     # some WBArea_... values come from NHDArea polygons, not NHDWaterbody. Filter dictionary for valid only.
#     flowline_wb_dict = {nhdplusid: nhd_wbarea_dict[nhdplusid] for nhdplusid, wb_permid in nhd_wbarea_dict.items() if
#                         wb_permid in valid_wb_ids}
#
#     with arcpy.da.UpdateCursor(nhd_cat_copy, ['NHDPlusID', 'Lake_PermID', 'Flowline_PermID']) as nhd_cat_copy_cursor:
#
#         # use UpdateCursor to "join" to get waterbody ids
#         for u_row in nhd_cat_copy_cursor:
#             nhdplusid = u_row[0]
#             lake_permid_flowline = None
#             lake_permid_sink = None
#
#             # like SELECT WBArea_Permanent_Identifier FROM nhd_cat LEFT JOIN nhd_flowline
#             if nhdplusid in flowline_wb_dict:
#                 lake_permid_flowline = flowline_wb_dict[nhdplusid]
#
#             # join to sinks to get sink to lake mapping
#             # like SELECT Permanent_Identifier FROM nhd_cat LEFT JOIN nhd_wb
#             if nhdplusid in nhd_wb_dict:
#                 lake_permid_sink = nhd_wb_dict[nhdplusid]
#
#             # concatenate & calculate update
#             if lake_permid_flowline:  # on network
#                 lake_permid = lake_permid_flowline
#
#             else:  # off network (sink)
#                 lake_permid = lake_permid_sink
#                 stream_permid = None
#
#             if nhdplusid in nhd_flowline_dict:  # catchment is not for a sink
#                 stream_permid = nhd_flowline_dict[nhdplusid]
#             else:  # catchment is for a sink
#                 stream_permid = None
#
#             # write the update
#             new_row = (nhdplusid, lake_permid, stream_permid)
#             nhd_cat_copy_cursor.updateRow(new_row)
#
#     return nhd_cat_copy
#
#
# def merge_lake_catchments(nhdplus_gdb, output_catchments_fc):
#     arcpy.env.workspace = 'in_memory'
#     catchments_assigned = assign_catchments_to_lakes(nhdplus_gdb, 'catchments_assigned')
#
#     # dissolve the lake catchments and separate out the stream catchments layer
#     stream_cats = AN.Select(catchments_assigned, 'stream_cats', 'Lake_PermID IS NULL')
#     lake_cats = AN.Select(catchments_assigned, 'lake_cats', 'Lake_PermID IS NOT NULL')
#     dissolved_lake_cats = DM.Dissolve(lake_cats, 'dissolved_lake_cats', ['Lake_PermID'])
#     DM.AddField(dissolved_lake_cats, 'NHDPlusID', 'DOUBLE')  # leave as all NULL on purpose
#
#     # # update each lake watershed shape so that it includes the entire lake/cannot extend beyond the lake.
#     # wb_shapes_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhdwaterbody, ['Permanent_Identifier', 'SHAPE@'])}
#     # with arcpy.da.UpdateCursor(dissolved_lake_cats, ['Lake_Permanent_Identifier', 'SHAPE@']) as u_cursor:
#     #     for row in u_cursor:
#     #         id, shape = row
#     #         wb_shape = wb_shapes_dict[id]
#     #         new_shape = shape.union(wb_shape)
#     #         u_cursor.updateRow((id, new_shape))
#     #
#     # # erase all lake catchments from stream catchments so there are no overlaps
#     # output_fc = AN.Update(stream_cats, dissolved_lake_cats, output_catchments_fc)
#     output_fc = DM.Merge([stream_cats, dissolved_lake_cats], output_catchments_fc)
#     DM.AddIndex(output_fc, 'Lake_PermID', 'lake_id_idx')
#     DM.AddIndex(output_fc, 'Flowline_PermID', 'stream_id_idx')
#     DM.Delete('in_memory')
#     return output_fc
#
#
# def calculate_waterbody_strahler(nhdplus_gdb, output_table):
#     """Output a table with a new field describing the Strahler stream order for each waterbody in the input GDB.
#
#     The waterbody's Strahler order will be defined as the highest Strahler order for an NHDFlowline artificial
#     path associated with that waterbody.
#
#     :param nhdplus_gdb: The NHDPlus HR geodatabase to calculate Strahler values for
#     :param output_table: The output table containing lake identifiers and the calculated field "lake_higheststrahler"
#
#     :return: ArcGIS Result object for output_table
#
#     """
#     nhd_wb = os.path.join(nhdplus_gdb, 'NHDWaterbody')
#     nhd_flowline = os.path.join(nhdplus_gdb, 'NHDFlowline')
#     nhd_vaa = os.path.join(nhdplus_gdb, 'NHDPlusFlowlineVAA')
#
#     # build dictionaries for the joins
#     nhd_wb_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_wb, ['Permanent_Identifier', 'NHDPlusID'])}
#     # filter upcoming dictionary to only include artificial flowlines (but with both waterbody and NHDArea ids)
#     nhd_flowline_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_flowline,
#                                                                    ['NHDPlusID', 'WBArea_Permanent_Identifier']) if
#                          r[1]}
#     # filter out flowlines we can't get strahler for NOW, so that loop below doesn't have to test
#     nhd_vaa_dict = {r[0]: r[1] for r in arcpy.da.SearchCursor(nhd_vaa, ['NHDPlusID', 'StreamOrde'])
#                     if r[0] in nhd_flowline_dict}
#     # filter out lines with uninitialized flow as they don't appear in nhd_vaa_dict
#     nhd_flowline_dict2 = {key: val for key, val in nhd_flowline_dict.items() if key in nhd_vaa_dict}
#
#     # set up new table
#     output_table = DM.CreateTable(os.path.dirname(output_table), os.path.basename(output_table))
#     DM.AddField(output_table, 'Lake_Permanent_Identifier', 'TEXT', field_length=40)
#     DM.AddField(output_table, 'NHDPlusID', 'DOUBLE')
#     DM.AddField(output_table, 'lake_higheststrahler', 'SHORT')
#     DM.AddField(output_table, 'lake_loweststrahler', 'SHORT')
#
#     # set up cursor
#     out_rows = arcpy.da.InsertCursor(output_table, ['Lake_Permanent_Identifier',
#                                                     'NHDPlusID',
#                                                     'lake_higheststrahler',
#                                                     'lake_loweststrahler'])
#
#     # function to call for each waterbody
#     nhd_flowline_dict_items = nhd_flowline_dict2.items()
#
#     def get_matching_strahlers(wb_permid):
#         matching_strahlers = [nhd_vaa_dict[flow_plusid] for flow_plusid, linked_wb_permid
#                               in nhd_flowline_dict_items if linked_wb_permid == wb_permid]
#         return matching_strahlers
#
#     # populate the table with the cursor
#     for wb_permid, nhdplusid in nhd_wb_dict.items():
#         strahlers = get_matching_strahlers(wb_permid)
#         if strahlers:
#             new_row = (wb_permid, nhdplusid, max(strahlers), min(strahlers))
#         else:
#             new_row = (wb_permid, nhdplusid, None, None)
#         out_rows.insertRow(new_row)
#
#     del out_rows
#
#     return output_table
#












