# Filename: InterLakeWatersheds.py

import os, shutil
import arcpy
import csiutils as cu

def aggregate_watersheds(nhd, watersheds, topoutfolder, filterlakes,
                        aggregate_method = ['interlake', 'cumulative']):
    if aggregate_method == 'interlake':
        file_append = 'IWS'
    elif aggregate_method == 'cumulative':
        file_append = 'CWS'

    # Naming Convention
    subregion_number = os.path.basename(nhd)
    subregion = subregion_number[4:8]
    outfolder = os.path.join(topoutfolder, subregion + file_append)
    if not os.path.exists(outfolder):
        os.mkdir(outfolder)

    # Projections:
    nad83 = arcpy.SpatialReference(4269)
    albers = arcpy.SpatialReference(102039)

    # NHD variables:
    flowline = os.path.join(nhd, "Hydrography", "NHDFlowline")
    waterbody = os.path.join(nhd, "Hydrography", "NHDWaterbody")
    network = os.path.join(nhd, "Hydrography", "HYDRO_NET")
    junction = os.path.join(nhd, "Hydrography", "HYDRO_NET_Junctions")
    arcpy.env.extent = waterbody

    # Make shapefiles for one hectare and ten hectare lakes that intersect flowlines.
    arcpy.FeatureClassToShapefile_conversion(waterbody, outfolder)
    waterbodyshp = os.path.join(outfolder, "NHDWaterbody.shp")
    waterbody_lyr = os.path.join(outfolder, "waterbody.lyr")
    arcpy.MakeFeatureLayer_management(waterbodyshp, waterbody_lyr)
    arcpy.SelectLayerByAttribute_management(waterbody_lyr, "NEW_SELECTION", '''"AreaSqKm">=0.04''')

    fcodes = (39000, 39004, 39009, 39010, 39011, 39012, 43600, 43613, 43615, 43617, 43618, 43619, 43621)
    whereClause = '''("AreaSqKm" >=0.04 AND "FCode" IN %s) OR ("FCode" = 43601 AND "AreqSqKm" >= 0.1)''' % (fcodes,)
    ##whereClause = '''"AreaSqKm" >=0.04 AND ("FCode" = 39000 OR "FCode" = 39004 OR\
    ##"FCode" = 39009 OR "FCode" = 39010 OR "FCode" = 39011 OR "FCode" = 39012 OR "FCode" = 43600 OR "FCode" = 43613 OR\
    ##"FCode" = 43615 OR "FCode" = 43617 OR "FCode" = 43618 OR "FCode" = 43619 OR "FCode" = 43621 OR ("FCode" = 43601 AND "AreaSqKm" >=0.1 ))'''
    arcpy.SelectLayerByAttribute_management(waterbody_lyr, "SUBSET_SELECTION", whereClause)

    all4ha = os.path.join(outfolder, "all4ha.shp")
    arcpy.CopyFeatures_management(waterbody_lyr, all4ha)

    arcpy.SelectLayerByLocation_management(waterbody_lyr, "INTERSECT", flowline, "", "SUBSET_SELECTION")

    try:
        filtershp = os.path.join(outfolder, "filter.shp")
        arcpy.Project_management(filterlakes, filtershp, nad83, '', albers)
        arcpy.SelectLayerByLocation_management(waterbody_lyr, "INTERSECT", filtershp, '', "SUBSET_SELECTION")

    except:
        pass

    fourha = os.path.join(outfolder, "fourha.shp")
    arcpy.CopyFeatures_management(waterbody_lyr, fourha)

    fourha_lyr = os.path.join(outfolder, "fourha.lyr")
    arcpy.MakeFeatureLayer_management(fourha, fourha_lyr)

    if aggregate_method == 'interlake':
        arcpy.SelectLayerByAttribute_management(fourha_lyr, "NEW_SELECTION", '''"AreaSqKm">=0.1''')

        tenha = os.path.join(outfolder, "tenha.shp")
        arcpy.CopyFeatures_management(fourha_lyr, tenha)

        tenhacenter = os.path.join(outfolder, "tenhacenter.shp")
        arcpy.FeatureToPoint_management(tenha, tenhacenter, "INSIDE")


    # Make shapefiles of junctions that intersect one hectare and ten hectare lakes.
    junction_lyr = os.path.join(outfolder, "junction.lyr")
    arcpy.MakeFeatureLayer_management(junction, junction_lyr)

    arcpy.SelectLayerByLocation_management(junction_lyr, "INTERSECT", fourha, '', "NEW_SELECTION")

    fourhajunction = os.path.join(outfolder, "fourhajunction.shp")
    arcpy.CopyFeatures_management(junction_lyr, fourhajunction)

    if aggregate_method == 'interlake':
        arcpy.SelectLayerByLocation_management(junction_lyr, "INTERSECT", tenha, '', "NEW_SELECTION")

        tenhajunction = os.path.join(outfolder, "tenhajunction.shp")
        arcpy.CopyFeatures_management(junction_lyr, tenhajunction)


    # Split lakes.
    arcpy.AddField_management(fourha, "ID", "TEXT")
    arcpy.CalculateField_management(fourha, "ID", '''"%s" % (!FID!)''', "PYTHON")
    arcpy.AddField_management(all4ha, "ID", "TEXT")
    arcpy.CalculateField_management(all4ha, "ID", '''"%s" % (!FID!)''', "PYTHON")

    lakes = os.path.join(outfolder, "lakes")
    if not os.path.exists(lakes):
        os.mkdir(lakes)

    arcpy.Split_analysis(all4ha, all4ha, "ID", lakes)

    # Iterate tracing.
    arcpy.env.workspace = lakes

    watersheds_lyr = os.path.join(outfolder, "watersheds.lyr")
    arcpy.MakeFeatureLayer_management(watersheds, watersheds_lyr)

    fcs = arcpy.ListFeatureClasses()
    fourhajunction_lyr = os.path.join(outfolder, "fourhajunction.lyr")
    arcpy.MakeFeatureLayer_management(fourhajunction, fourhajunction_lyr)


    # Create folder for final output
    agg_ws = os.path.join(outfolder, file_append)
    if not os.path.exists(agg_ws):
        os.mkdir(agg_ws)

    if aggregate_method == 'interlake':
        tenhajunction_lyr = os.path.join(outfolder, "tenhajunction.lyr")
        arcpy.MakeFeatureLayer_management(tenhajunction, tenhajunction_lyr)

    arcpy.AddMessage("Starting iteration.")

    for fc in fcs:

        arcpy.RefreshCatalog(outfolder)
        name = os.path.splitext(fc)[0]
        arcpy.AddMessage("Processing " + name + ".")
        # Sets the output to in memory:
        lakes = "in_memory"
        # Repair the lake geometery if needed.
        arcpy.RepairGeometry_management(fc)
        # Make sure the lake's own watershed gets added (merged) back in to the final aggregated watershed:
        # Make a centroid for the lake, then intersect it with watersheds, then merge it with the previous sheds made above.
        center = os.path.join(lakes, "center" + name)
        arcpy.FeatureToPoint_management(fc, center, "INSIDE")

        arcpy.SelectLayerByLocation_management(watersheds_lyr, "INTERSECT", center, '', "NEW_SELECTION")
        ownshed = os.path.join(lakes, "ownshed" + name)
        arcpy.CopyFeatures_management(watersheds_lyr, ownshed)

        if aggregate_method == 'interlake':
            # Select 10 hectare lake junctions that don't intersect the target lake.
            arcpy.SelectLayerByLocation_management(tenhajunction_lyr, "INTERSECT", fc, '', "NEW_SELECTION")
            arcpy.SelectLayerByLocation_management(tenhajunction_lyr, "INTERSECT", fc, '', "SWITCH_SELECTION")

        # Select 4 hectare lake junctions that do intersect it.
        arcpy.SelectLayerByLocation_management(fourhajunction_lyr, "INTERSECT", fc, '', "NEW_SELECTION")
        # Copy junctions
        lakejunction = os.path.join(lakes, "junct" + name)
        arcpy.CopyFeatures_management(fourhajunction_lyr, lakejunction)

        try:
            # Trace the network upstream from the junctions from above, stopping at ten hectare junctions.
            if aggregate_method == 'interlake':
                arcpy.TraceGeometricNetwork_management(network, os.path.join(lakes, "im" + name + "tracelyr"), lakejunction, "TRACE_UPSTREAM", tenhajunction_lyr)
            elif aggregate_method == 'cumulative':
                arcpy.TraceGeometricNetwork_management(network, os.path.join(lakes, "im" + name + "tracelyr"), lakejunction, "TRACE_UPSTREAM")
            trace = os.path.join(lakes, "im" + name + "tracelyr", "NHDFlowline")

            # Write the trace
            traceshp = os.path.join(lakes, "im" + name + "trace")
            arcpy.CopyFeatures_management(trace, traceshp)

            # Make a layer from the trace
            tracesel = os.path.join(lakes, "im" + name + "tracesellyr")
            arcpy.MakeFeatureLayer_management(traceshp, tracesel)

            # Select from the trace lines those that don't have their midpoint in the lake
            arcpy.SelectLayerByLocation_management(tracesel, "HAVE_THEIR_CENTER_IN", fc, '', "NEW_SELECTION")
            arcpy.SelectLayerByLocation_management(tracesel, "HAVE_THEIR_CENTER_IN", fc, '', "SWITCH_SELECTION")
            # Select watersheds that intersect the trace
            arcpy.SelectLayerByLocation_management(watersheds_lyr, "INTERSECT", tracesel, '', "NEW_SELECTION")

            if aggregate_method == 'interlake':
                # Remove watersheds that contain a 10 hectare lake's center from previous selection
                arcpy.SelectLayerByLocation_management(watersheds_lyr, "INTERSECT", tenhacenter, '', "REMOVE_FROM_SELECTION")

            sheds = os.path.join(lakes, "im" + name + "sheds")
            arcpy.CopyFeatures_management(watersheds_lyr, sheds)

            sheds_lyr = os.path.join(lakes, "im" + name + "shedslyr")
            arcpy.MakeFeatureLayer_management(sheds, sheds_lyr)

        except:
            arcpy.AddMessage("Isolated shed.")

        sheds3 = os.path.join(lakes, "sheds3" + name)
        try:
            arcpy.Merge_management([sheds,ownshed], sheds3)

        except:
            arcpy.CopyFeatures_management(ownshed, sheds3)

        # Dissolve the aggregate watershed if it has more than one polygon
        polynumber = int(arcpy.GetCount_management(sheds3).getOutput(0))
        pre = os.path.join(lakes, "pre" + name)

        if polynumber > 1:
            arcpy.AddField_management(sheds3, "Dissolve", "TEXT")
            arcpy.CalculateField_management(sheds3, "Dissolve", "1", "PYTHON")
            arcpy.Dissolve_management(sheds3, pre)

        elif polynumber < 2:
            arcpy.CopyFeatures_management(sheds3, pre)

        # Get the permanent id from the feature and add it to output shed
        field = "Permanent_"
        cursor = arcpy.SearchCursor(fc)
        for row in cursor:
            id = row.getValue(field)
        arcpy.AddField_management(pre, "NHD_ID", "TEXT")
        arcpy.CalculateField_management(pre, "NHD_ID", '"{0}"'.format(id), "PYTHON")
        # Erase the lakes own geometry from its watershed
        arcpy.Erase_analysis(pre,fc, os.path.join(agg_ws, file_append + name + ".shp"))


        # Delete intermediate in_memory fcs and variables
        temp_items = [lakejunction, trace, traceshp, tracesel, sheds, sheds_lyr,
                    center, sheds2, sheds3, pre, fc, ownshed]
        cu.cleanup(temp_items)

        arcpy.ResetEnvironments()

def main():
    nhd = arcpy.GetParameterAsText(0)
    watersheds = arcpy.GetParameterAsText(1)
    topoutfolder = arcpy.GetParameterAsText(2)
    filterlakes = arcpy.GetParameterAsText(3)
    interlake_watersheds(nhd, watersheds, topoutfolder, filterlakes)

def test():
    pass

if __name__ == '__main__':
    main()

















