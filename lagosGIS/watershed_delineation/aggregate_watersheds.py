# filename: aggregate_watersheds.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): LOCUS
# tool type: re-usable (ArcGIS Toolbox)

import os
import re

import arcpy
from arcpy import analysis as AN, management as DM

import lagosGIS
from lagosGIS.NHDNetwork import NHDNetwork


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
    temp_gdb = lagosGIS.create_temp_GDB('aggregate_watersheds')
    albers = arcpy.SpatialReference(5070)

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
        interlake_erasable_regions = nhd_network.define_interlake_erasable()
        # then convert network to use barriers
        nhd_network.activate_10ha_lake_stops()

    # Step 3: Run the desired traces according to the mode. trace[id] = list of all flowline IDS in trace
    nhd_network.set_start_ids(matching_ids)
    traces = nhd_network.trace_up_from_waterbody_starts()

    # Establish output fc
    merged_sheds = DM.CreateFeatureclass('in_memory', 'merged_sheds', 'POLYGON', spatial_reference=albers)
    DM.AddField(merged_sheds, 'Permanent_Identifier', 'TEXT', field_length=40)
    sheds_cursor = arcpy.InsertCursor(merged_sheds, ['Permanent_Identifier', 'SHAPE@'])

    # Looping watersheds processing
    # The specific recipe for speed in this loop (about 0.8 seconds per loop/drainage lake):
    # 1) The watersheds dataset being queried must have an index. (use temp_gdb instead of in_memory above)
    # 2) It is faster to AN.Select from a feature layer of the indexed lake/watershed dataset than the dataset itself.
    # 3) Dissolve must work on something in_memory (not a selected layer on disk) for a big speed increase.
    # 4) Extraneous fields are NOT ignored by Dissolve and slow it down, so they were removed earlier.
    # 5) Spatial queries were actually quite fast but picked up extraneous catchments, so we will not use that method.
    # 6) Deletions in the loop waste time (1/3 second per loop) and overwriting causes no problems.
    # 7) Avoid processing any isolated or headwater lakes, no upstream aggregation necessary.
    arcpy.AddMessage("Accumulating watersheds according to traces...")
    counter = 0
    single_catchment_ids = []
    arcpy.env.overwriteOutput = True
    arcpy.SetLogHistory(False)

    # START LOOP
    for lake_id in matching_ids:
        # *print updates roughly every 5 minutes
        counter += 1
        if counter % 250 == 0:
            print("{} of {} lakes completed...".format(counter, len(matching_ids)))

        # Loop Step 1: Determine if the lake has upstream network. If not, skip accumulation.
        trace_permids = traces[lake_id]
        if len(trace_permids) <= 2:  # headwater lakes have trace length = 2 (lake and flowline)
            single_catchment_ids.append(lake_id)
        else:
            # Loop Step 2: Select catchments with their Permanent_Identifier in the lake's upstream network trace.
            watersheds_query = 'Permanent_Identifier IN ({})'.format(','.join(['\'{}\''.format(id)
                                                                               for id in trace_permids]))
            selected_watersheds = AN.Select(watersheds_lyr1, 'selected_watersheds', watersheds_query)

            # Loop Step 3: Make a single, hole-free catchment polygon.
            this_watershed_holes = DM.Dissolve(selected_watersheds, 'this_watershed_holes')  # sheds has selection
            no_holes = DM.EliminatePolygonPart(this_watershed_holes, 'no_holes', 'PERCENT', part_area_percent='99.999')

            # Loop Step 4: Erase the lake from its own shed as well as any lakes along edges (not contained ones).
            this_lake_query = "Permanent_Identifier = '{}'".format(lake_id)
            DM.SelectLayerByAttribute(waterbody_lyr, 'NEW_SELECTION', this_lake_query)
            lakeless_watershed = arcpy.Erase_analysis(no_holes, waterbody_lyr, 'lakeless_watershed')

            # Loop Step 5: If interlake mode, erase OTHER off-network 10ha+ lake catchments.
            # Create dissolved, hole-free subnetwork polygons before erasing.
            if mode <> 'interlake':
                this_watershed = lakeless_watershed
            # Loop Step 5a: Select matching erasable regions (see NHDNetwork.define.interlake_erasable).
            else:
                tenha_sinks_query = 'Permanent_Identifier IN ({})'.format(
                    ','.join(['\'{}\''.format(id) for id in interlake_erasable_regions[lake_id]]))
                DM.SelectLayerByAttribute(watersheds_lyr2, 'NEW_SELECTION', tenha_sinks_query)
                DM.SelectLayerByLocation(watersheds_lyr2, 'INTERSECT', lakeless_watershed,
                                         selection_type='SUBSET_SELECTION')
                erase_count = int(DM.GetCount(watersheds_lyr2).getOutput(0))
                if erase_count == 0:
                    this_watershed = lakeless_watershed

                # Loop Step 5b: Make a single, hole-free polygon for each subnetwork.
                else:
                    other_tenha = DM.CopyFeatures(watersheds_lyr2, 'other_tenha')  # dissolves faster, weird but true
                    other_tenha_dissolved = DM.Dissolve(other_tenha, 'other_tenha_dissolved')
                    other_tenha_holeless = DM.EliminatePolygonPart(other_tenha_dissolved, 'other_tenha_holeless',
                                                                   'PERCENT',
                                                                   part_area_percent='99.999')

                    # Loop Step 5c: Erase the subnetworks.
                    this_watershed = arcpy.Erase_analysis(lakeless_watershed, other_tenha_holeless, 'this_watershed')

                    # handles very rare situation
                    # where a catchment entirely surrounded by isolated 10ha lakes is erased by their dissolved poly
                    if int(DM.GetCount(this_watershed).getOutput(0)) == 0:
                        safe_erase = arcpy.Erase_analysis(other_tenha_holeless, this_watershed_holes, 'safe_erase')
                        this_watershed = arcpy.Erase_analysis(lakeless_watershed, safe_erase, 'this_watershed')

            # Loop Step 6: Save current watershed to merged results feature class.
            this_watershed_geom = DM.CopyFeatures(this_watershed, arcpy.Geometry())
            sheds_cursor.insertRow([lake_id, this_watershed_geom])

    arcpy.env.overwriteOutput = False
    arcpy.SetLogHistory(True)

    # Step 4: For all isolated/headwater lakes, select the correct catchments and erase focal lakes from their own sheds
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
        DM.Append(lakeless_watersheds, merged_sheds, 'NO_TEST')
        for item in [these_lakes, these_watersheds, lakeless_watersheds]:
            DM.Delete(item)



    # Step 5: Fix in-island lakes, if any are present in the subregion. (140 lakes in U.S., in 53 subregions)
    out_count = int(DM.GetCount(merged_sheds).getOutput(0))
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
        DM.Append(island_sheds, merged_sheds, 'NO_TEST')
        for item in [islands, islands_holeless, islands_lyr, island_sheds]:
            DM.Delete(item)

    # Step 6: Identify inlets and flag whether each watershed extends to include one.
    inlets = set(nhd_network.identify_subregion_inlets())
    partial_test = {k: set(v).intersection(inlets) for k, v in traces.items()}
    DM.AddField(merged_sheds, 'includeshu4inlet', 'TEXT', field_length=1)
    with arcpy.da.UpdateCursor(merged_sheds, ['Permanent_Identifier', 'includeshu4inlet']) as u_cursor:
        for row in u_cursor:
            permid, inflag = row
            inflag = 'Y' if partial_test[permid] else 'N'
            u_cursor.updateRow((permid, inflag))

    # Step 7: Clean up results a bit and output results: eliminate slivers smaller than NHD raster cell, clip to HU4

    refined = DM.EliminatePolygonPart(merged_sheds, 'refined1', 'AREA', part_area='99', part_option='ANY')
    result = AN.Clip(refined, hu4, output_fc)
    try:
        DM.DeleteField(result, 'ORIG_FID')
    except:
        pass

    # DELETE/CLEANUP: first fcs to free up temp_gdb, then temp_gdb
    for item in [waterbody_lyr, watersheds_lyr1, watersheds_lyr2,
                 hu4, waterbody_mem, waterbody_holeless, watersheds_simple,
                 merged_sheds, refined]:
        DM.Delete(item)
    DM.Delete(temp_gdb)

    # Add warning if any missing
    final_count = int(DM.GetCount(result).getOutput(0))
    if final_count < len(matching_ids):
        output_ids = {r[0] for r in arcpy.da.SearchCursor(output_fc, 'Permanent_Identifier')}
        missing = list(set(matching_ids).difference(output_ids))
        arcpy.AddWarning("The following lakes do not have watersheds in the output: {}".format('\n'.join(missing)))
    return result


def main():
    catchments_fc = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(1)
    eligible_lakes_fc = arcpy.GetParameterAsText(2)
    output_fc = arcpy.GetParameterAsText(3)
    mode = arcpy.GetParameterAsText(4)
    aggregate_watersheds(catchments_fc, nhd_gdb, eligible_lakes_fc, output_fc,
                         mode)


if __name__ == '__main__':
    main()
