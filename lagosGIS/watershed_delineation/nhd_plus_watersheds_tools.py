# filename: nhd_plus_watersheds_tools.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)--tools called in individual scripts to make tools

import os
from datetime import datetime as dt
import subprocess as sp
from collections import defaultdict
from arcpy import management as DM
from arcpy import analysis as AN
from arcpy.sa import *
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
    1) include all LAGOS lakes as pour points taking precedence over flowlines,
    2) remove any waterbodies <1ha that were erroneously permitted as sinks in NHDPlus (those with "NHDWaterbody closed
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

    # IDENTIFY ERRONEOUS SINKS
    # due to burn/catseed errors in NHD, we are removing all sinks marked "NHDWaterbody closed lake" (SC)
    # remove from existing raster so we don't have to duplicate their flowline processing steps
    # in regions with no error: no change, correctly indicated closed lakes would be removed but we have overwritten
    # them with our own lake poly seeds anyway.
    sink = os.path.join(nhdplus_gdb, 'NHDPlusSink')
    sinks_to_remove = [r[0] for r in arcpy.da.SearchCursor(sink, ['GridCode'], "PurpCode = 'SC'")]

    # Find out if any of the selected sink codes are actually in the raster
    gridcodes_in_raster = set([r[0] for r in arcpy.da.SearchCursor(combined, 'VALUE')])
    removable_codes = gridcodes_in_raster.intersection(sinks_to_remove)

    if removable_codes:
        arcpy.AddMessage("Modifying catseed raster to clean lake seeds...")
        arcpy.CheckOutExtension('Spatial')
        cleaned = arcpy.sa.SetNull(combined, combined, 'VALUE in ({})'.format(','.join(['{}'.format(id)                                                                          for id in removable_codes])))
        cleaned.save(output_raster)
        arcpy.CheckInExtension('Spatial')
    else:
        arcpy.CopyRaster_management(combined, output_raster)

    arcpy.Delete_management(lake_seeds)
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
    # ----- SETUP -----------------------------------------------------------------------------------------------------
    # workspace will be set to hard drive if uncompressed hydrodem is > 8GB, prevents strange
    # outputs where replacement raster is assigned in more places than it should be or random
    # NoData gaps appear. Memory wasn't maxed out and neither was temp raster storage space, but
    # this works anyway using a limit of 8GB on my 64GB machine.
    # mostly affects subregions ['0902', '1018', '1109', '1710', '1209', '1304', '1606', '1701', '1702']
    desc = arcpy.Describe(hydrodem_raster)
    uncompressed_size = (float(desc.width) * desc.height * 4)/(2**30)
    if uncompressed_size >= 8:
        temp_gdb = lagosGIS.create_temp_GDB('revise_hydrodem')
        arcpy.env.workspace = temp_gdb
    else:
        temp_gdb = ''
        arcpy.env.workspace = 'in_memory'

    # per suggestion by Price here
    # https://community.esri.com/people/curtvprice/blog/2017/03/03/temporary-rasters-in-arcpy
    arcpy.env.scratchWorkspace = os.path.dirname(lagos_catseed_raster)

    # remaining env settings
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = hydrodem_raster
    arcpy.env.extent = hydrodem_raster
    projection = arcpy.SpatialReference(102039)
    arcpy.env.outputCoordinateSystem = projection
    arcpy.CheckOutExtension('Spatial')

    # ----- ADD LAGOS SINKS ---------------------------------------------------------------------------------------
    # identify valid sinks
    network = NHDNetwork(nhdplus_gdb)
    waterbody_ids = network.define_lakes(strict_minsize=True, force_lagos=True).keys()
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

    # only permit sinks that are in the catseed raster, i.e. they are in the LAGOS lake population
    sinks_raster = (IsNull(Raster(sinks_raster0)) == 0) & (IsNull(lagos_catseed_raster) == 0)
    centroids_raster = ((IsNull(Raster(centroids_raster0)) == 0) & sinks_raster)

    # burn in the sink lakes and add the nodata protection in the center
    arcpy.AddMessage("Burning sinks...")
    areal_drop = 10000 # in cm, so 100m elevation drop
    filldepth = Raster(filldepth_raster)
    lagos_catseed = Raster(lagos_catseed_raster)

    # operations combined here for processing speed (fewer temporary rasters)
    # first two terms inside SetNull generate the unfilled hydro raster and third term burns in sinks, like so
    # unfilled_hydrodem = Raster(hydrodem_raster) - Con(IsNull(filldepth), 0, filldepth)
    # with_burned_lakes = unfilled_hydrodem - (areal_drop * sinks_raster)
    # the setnull around the whole thing sets the nodata protection for the lake
    protected = SetNull(centroids_raster == 1, \
                    (Raster(hydrodem_raster) - Con(IsNull(filldepth), 0, filldepth) - (areal_drop * sinks_raster)))

    # -----REMOVE POTENTIAL EXCESSIVE NHDPLUS HR SINKS--------------------------------------------------------------
    # remove all fill-protected lakes that are NOT also in our modified pour points--these are the erroneous sinks
    arcpy.AddMessage("Removing extraneous sinks (if any)...")
    nhdplus_sink = os.path.join(nhdplus_gdb, 'NHDPlusSink')
    nhdplus_closed = arcpy.Select_analysis(nhdplus_sink, 'nhdplus_closed', "PurpCode = 'SC'")
    nhdplus_closed_ras0 = arcpy.PointToRaster_conversion(nhdplus_closed, "OBJECTID", "nhdplus_closed_ras0", cellsize=10)
    nhdplus_closed_ras = IsNull(Raster(nhdplus_closed_ras0)) == 0

    # use raster calculator to fill nodata with min value that surrounds it (lake is flattish)
    replacement = arcpy.sa.FocalStatistics(protected, statistics_type='MINIMUM')  # assign lake elevation value

    # fill in NoData cells with "replacement" value,
    # IF they are a NoData cell used for an NHDWaterbody closed lake sink in NHDPlus (nhdplus_closed_raster == 1)
    # AND they are not inside a LAGOS lake (IsNull(lagos_catseed_raster) == 1).
    # ELSE use the burned values from before but also protect LAGOS lakes with central NoData value
    result = Con((nhdplus_closed_ras) & (IsNull(lagos_catseed)), replacement, protected)
    result.save(out_raster)

    # cleanup
    arcpy.CheckInExtension('Spatial')
    for item in ['sink_lakes', 'sink_centroids', 'sinks_raster0', 'centroids_raster0',
                 'sinks_raster', 'centroids_raster', 'protected', 'nhdplus_closed', 'nhdplus_closed_ras0',
                 'nhdplus_closed_ras', 'replacement']:
        arcpy.Delete_management(item)
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

def flow_direction(hydrodem_raster, nhd_fdr, flow_direction_raster_out):
    """
    Create the flow direction raster for the subregion.
    :param hydrodem_raster: The modified or final hydrodem raster
    :param nhd_fdr: The fdr raster from NHDPlus
    :param flow_direction_raster_out: The output raster containing the flow directions
    :return:
    """
    arcpy.CheckOutExtension('Spatial')
    arcpy.AddMessage('Flow direction started at {}...'.format(dt.now().strftime("%Y-%m-%d %H:%M:%S")))
    flow_dir = arcpy.sa.FlowDirection(hydrodem_raster)
    # enforce same bounds as NHD fdr, so catchments have same HU4 boundary
    flow_dir_clipped = arcpy.sa.Con(arcpy.sa.IsNull(nhd_fdr), nhd_fdr, flow_dir)
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

    # delineate watersheds with ArcGIS Watershed tool, then convert to polygon
    arcpy.AddMessage("Delineating catchments...")
    sheds = arcpy.sa.Watershed(flowdir_raster, catseed_raster, 'Value')
    arcpy.AddMessage("Watersheds complete.")
    sheds_poly = arcpy.RasterToPolygon_conversion(sheds, 'sheds_poly', 'NO_SIMPLIFY', 'Value')
    DM.AlterField(sheds_poly, 'gridcode', 'GridCode', clear_field_alias=True)

    arcpy.AddMessage("Linking identifiers...")
    # make a nhdpid: permid dict for NHDPlus
    if nhd_network.plus:
        if not nhd_network.nhdpid_flowline:
            nhd_network.map_nhdpid_to_flowlines()
        if not nhd_network.nhdpid_waterbody:
            nhd_network.map_waterbody_to_nhdpids()
        nhdpid_combined = defaultdict(list)
        for d in (nhd_network.nhdpid_flowline, nhd_network.nhdpid_waterbody):
            for k, v in d.items():
                nhdpid_combined[k] = v

    # re-assign lake ArtificialPath catchments to have the lake Gridcode and dissolve into lake catchment
    # here's why: some catseed cells for ArtificialPaths remain after modifying catseed to put lake raster outlets
    # over the NHDPlus catseed layer. Couldn't re-create catseed from vectors to match NHDPlus snap, so using
    # this solution instead.
    update_fields = ['GridCode', 'NHDPlusID', 'SourceFC', 'VPUID']
    if not nhd_network.plus:
        update_fields.append('Permanent_Identifier')
    gridcode_dict = {r[0]: r[1:] for r in arcpy.da.SearchCursor(gridcode_table, update_fields)}
    flowplusid_wbpermid = {r[0]:r[1] for r in arcpy.da.SearchCursor(nhd_network.flowline,
                            ['NHDPlusID', 'WBArea_Permanent_Identifier'], "WBArea_Permanent_Identifier IS NOT NULL")}
    wbpermid_wbgrid = {nhdpid_combined.get(v[0]):k for k, v in gridcode_dict.items() if v[1] == 'NHDWaterbody'}
    # make dict with flowline gridcode as key and waterbody gridcode as value
    flowgrid_wbgrid_0 = {k:wbpermid_wbgrid.get(flowplusid_wbpermid.get(v[0])) for k, v in gridcode_dict.items()}
    valid_wb_gridcodes = [r[0] for r in arcpy.da.SearchCursor(sheds_poly, 'GridCode')]
    flowgrid_wbgrid = {k:v for k, v in flowgrid_wbgrid_0.items() if v and v in valid_wb_gridcodes}

    # then replace gridcode in catchments to be waterbody if it belongs to ArtificialPath
    with arcpy.da.UpdateCursor(sheds_poly, ['Gridcode']) as cursor:
        for row in cursor:
            if row[0] in flowgrid_wbgrid:
                row[0] = flowgrid_wbgrid[row[0]]
                cursor.updateRow(row)

    # finally, dissolve on gridcode
    dissolved = DM.Dissolve(sheds_poly, 'dissolved', 'GridCode')
    arcpy.AddMessage("Watersheds converted to vector.")

    # "Join" to the other identifiers via GridCode
    DM.AddField(dissolved, 'NHDPlusID', 'DOUBLE')
    DM.AddField(dissolved, 'SourceFC', 'TEXT', field_length=20)
    DM.AddField(dissolved, 'VPUID', 'TEXT', field_length=8)
    DM.AddField(dissolved, 'Permanent_Identifier', 'TEXT', field_length=40)
    DM.AddField(dissolved, 'On_Main_Network', 'TEXT', field_length=1)

    # calculate whether the watershed is on the main network
    on_network = set(nhd_network.trace_up_from_hu4_outlets())

    # update table with ids and flags
    print('Adding identifiers to dissolved watersheds...')
    output_fields = ['GridCode', 'NHDPlusID', 'SourceFC', 'VPUID', 'Permanent_Identifier',
                     'On_Main_Network']
    with arcpy.da.UpdateCursor(dissolved, output_fields) as u_cursor:
        for row in u_cursor:
            gridcode, nhdpid, sourcefc, vpuid, permid, onmain = row
            if gridcode != 0:
                if nhd_network.plus:
                    nhdpid, sourcefc, vpuid = gridcode_dict[gridcode]
                else:
                    nhdpid, sourcefc, vpuid, permid = gridcode_dict[gridcode]
            if not permid:
                permid = nhdpid_combined.get(nhdpid)
            onmain = 'Y' if permid in on_network else 'N'
            u_cursor.updateRow((gridcode, nhdpid, sourcefc, vpuid, permid, onmain))

    def reassign_slivers_to_lakes(catchments_fc):
        # remove slight overlaps with neighboring lakes that are in the LAGOS population
        output_fields.insert(0, output_fields.pop(4))
        waterbody_cat_dict = {r[0]:r[1:] for r in arcpy.da.SearchCursor(
            catchments_fc, output_fields, "SourceFC = 'NHDWaterbody'")}
        waterbody_query = 'Permanent_Identifier IN ({})'.format(
            ','.join(['\'{}\''.format(id) for id in waterbody_cat_dict.keys()]))
        waterbody = arcpy.Select_analysis(nhd_network.waterbody, 'waterbody', waterbody_query)
        waterbody_only = lagosGIS.select_fields(waterbody, 'waterbody_only', ['Permanent_Identifier'], convert_to_table=False)
        arcpy.AddMessage("Finding conflicting lake/watershed slivers...")
        catchments_lyr = arcpy.MakeFeatureLayer_management(catchments_fc)
        arcpy.SelectLayerByLocation_management(catchments_lyr, 'INTERSECT', waterbody_only)
        union = arcpy.Union_analysis([catchments_lyr, waterbody_only], 'union')
        arcpy.SelectLayerByAttribute_management(catchments_lyr, 'SWITCH_SELECTION')
        changeless_sheds = arcpy.CopyFeatures_management(catchments_lyr, 'changeless_sheds')

        # move slivers in union into the lake watershed as long as they intersect the lake
        with arcpy.da.UpdateCursor(union, ['Permanent_Identifier_1'] + output_fields) as cursor:
            for row in cursor:
                if row[0] != '': # union produces blank strings instead of nulls
                    row[1] = row[0] # if lake_id, then use it as the catchment id (move slivers into lake catchment)
                    row[2:] = waterbody_cat_dict.get(row[1]) # update fields to match waterbody vals
                cursor.updateRow(row)

        arcpy.DeleteField_management(union, 'Permanent_Identifier_1')
        arcpy.DeleteField_management(union, 'FID_1')
        arcpy.AddMessage("Reconstituting watersheds...")
        reassigned = arcpy.Dissolve_management(union, 'reassigned', output_fields)
        merged = arcpy.Append_management(reassigned, changeless_sheds, 'NO_TEST')

        for item in [waterbody, waterbody_only, catchments_lyr, union, reassigned]:
            arcpy.Delete_management(item)
        return merged

    arcpy.AddMessage("Reassigning slivers...")
    reassigned_output = reassign_slivers_to_lakes(dissolved)
    arcpy.CopyFeatures_management(reassigned_output, output_fc)

    for item in [sheds, sheds_poly, dissolved, reassigned_output]:
        arcpy.Delete_management(item)

    return output_fc