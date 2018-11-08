# Filename : LakeClass.py
# Author : Scott Stopyak, Geographer, Michigan State University
# Purpose : Classify lakes according to their connectivity to the hydrologic network using only NHD as input.
# Modified: Nicole Smith, 2017

import os
import arcpy
from arcpy import management as DM
import csiutils as cu

XY_TOLERANCE = '1 Meters'

def classify_lakes(nhd, out_feature_class, exclude_intermit_flowlines = False, debug_mode=False):
    if debug_mode:
        arcpy.env.overwriteOutput = True
        temp_gdb = cu.create_temp_GDB('classify_lake_connectivity')
        arcpy.env.workspace = temp_gdb
        arcpy.AddMessage('Debugging workspace located at {}'.format(temp_gdb))

    else:
        arcpy.env.workspace = 'in_memory'

    if arcpy.Exists("temp_fc"):
        print("There is a problem here.")
        raise Exception

    # Tool temporary feature classes
    temp_fc = "temp_fc"
    csiwaterbody_10ha = "csiwaterbody_10ha"
    nhdflowline_filtered = "nhdflowline_filtered"
    dangles = "dangles"
    start = "start"
    end = "end"
    startdangles = "startdangles"
    enddangles = "enddangles"
    non_artificial_end = "non_artificial_end"
    flags_10ha_lake_junctions = "flags_10ha_lake_junctions"
    midvertices = "midvertices"
    non10vertices = "non10vertices"
    non10junctions = "non10junctions"
    all_non_flag_points = "all_non_flag_points"
    barriers = "barriers"
    trace1_junctions = "trace1_junctions"
    trace1_flowline = "trace1_flowline"
    trace2_junctions = "trace2junctions"
    trace2_flowline = "trace2_flowline"

    # Clean up workspace in case of bad exit from prior run in same session.
    this_tool_layers = ["dangles_lyr", "nhdflowline_lyr", "junction_lyr", "midvertices_lyr", "all_non_flag_points_lyr",
                        "non10vertices_lyr", "out_fc_lyr", "trace1", "trace2"]
    this_tool_temp = [temp_fc, csiwaterbody_10ha, nhdflowline_filtered, dangles, start, end, startdangles, enddangles,
                      non_artificial_end, flags_10ha_lake_junctions, midvertices, non10vertices, non10junctions,
                      all_non_flag_points, barriers, trace1_junctions, trace1_flowline, trace2_junctions,
                      trace2_flowline]
    for item in this_tool_layers + this_tool_temp:
        try:
            DM.Delete(item)
        except:
            pass

    # Local variables:
    nhdflowline = os.path.join(nhd, "Hydrography", "NHDFLowline")
    nhdjunction = os.path.join(nhd, "Hydrography", "HYDRO_NET_Junctions")
    nhdwaterbody = os.path.join(nhd, "Hydrography", "NHDWaterbody")
    network = os.path.join(nhd, "Hydrography", "HYDRO_NET")

    # Get lakes, ponds and reservoirs over a hectare.
    #csi_population_filter = '''"AreaSqKm" >=0.01 AND\
    #"FCode" IN (39000,39004,39009,39010,39011,39012,43600,43613,43615,43617,43618,43619,43621)'''
    all_lakes_reservoirs_filter = '''"FType" IN (390, 436)'''

    # Can't see why we shouldn't just attribute all lakes and reservoirs
    # arcpy.Select_analysis(nhdwaterbody, "csiwaterbody", lake_population_filter)
    arcpy.AddMessage("Initializing output.")
    if exclude_intermit_flowlines:
        DM.CopyFeatures(out_feature_class, temp_fc)
        DM.Delete(out_feature_class)
    else:
        arcpy.Select_analysis(nhdwaterbody, temp_fc, all_lakes_reservoirs_filter)


    # Get lakes, ponds and reservoirs over 10 hectares.
    lakes_10ha_filter = '''"AreaSqKm" >= 0.1 AND "FType" IN (390, 436)'''
    arcpy.Select_analysis(nhdwaterbody, csiwaterbody_10ha, lakes_10ha_filter)

    # Exclude intermittent flowlines, if requested
    if exclude_intermit_flowlines:
        flowline_where_clause = '''"FCode" NOT IN (46003,46007)'''
        nhdflowline = arcpy.Select_analysis(nhdflowline, nhdflowline_filtered, flowline_where_clause)

    # Make dangle points at end of nhdflowline
    DM.FeatureVerticesToPoints(nhdflowline, dangles, "DANGLE")
    DM.MakeFeatureLayer(dangles, "dangles_lyr")

    # Isolate start dangles from end dangles.
    DM.FeatureVerticesToPoints(nhdflowline, start, "START")
    DM.FeatureVerticesToPoints(nhdflowline, end, "END")

    DM.SelectLayerByLocation("dangles_lyr", "ARE_IDENTICAL_TO", start)
    DM.CopyFeatures("dangles_lyr", startdangles)
    DM.SelectLayerByLocation("dangles_lyr", "ARE_IDENTICAL_TO", end)
    DM.CopyFeatures("dangles_lyr", enddangles)

    # Special handling for lakes that have some intermittent flow in and some permanent
    if exclude_intermit_flowlines:
        DM.MakeFeatureLayer(nhdflowline, "nhdflowline_lyr")
        DM.SelectLayerByAttribute("nhdflowline_lyr", "NEW_SELECTION", '''"WBArea_Permanent_Identifier" is null''')
        DM.FeatureVerticesToPoints("nhdflowline_lyr", non_artificial_end, "END")
        DM.SelectLayerByAttribute("nhdflowline_lyr", "CLEAR_SELECTION")

    arcpy.AddMessage("Found source area nodes.")

    # Get junctions from lakes >= 10 hectares.
    DM.MakeFeatureLayer(nhdjunction, "junction_lyr")
    DM.SelectLayerByLocation("junction_lyr", "INTERSECT", csiwaterbody_10ha, XY_TOLERANCE,
                                           "NEW_SELECTION")

    DM.CopyFeatures("junction_lyr", flags_10ha_lake_junctions)
    arcpy.AddMessage("Found lakes >= 10 ha.")

    # Make points shapefile and layer at flowline vertices to act as potential flags and/or barriers.
    arcpy.AddMessage("Tracing...")
    DM.FeatureVerticesToPoints(nhdflowline, midvertices, "MID")
    DM.MakeFeatureLayer(midvertices, "midvertices_lyr")

    # Get vertices that are not coincident with 10 hectare lake junctions.
    DM.SelectLayerByLocation("midvertices_lyr", "INTERSECT", flags_10ha_lake_junctions, "",
                                           "NEW_SELECTION")
    DM.SelectLayerByLocation("midvertices_lyr", "INTERSECT", flags_10ha_lake_junctions, "",
                                           "SWITCH_SELECTION")
    DM.CopyFeatures("midvertices_lyr", non10vertices)

    # Get junctions that are not coincident with 10 hectare lake junctions.
    DM.SelectLayerByLocation("junction_lyr", "INTERSECT", flags_10ha_lake_junctions, "",
                                           "NEW_SELECTION")
    DM.SelectLayerByLocation("junction_lyr", "INTERSECT", flags_10ha_lake_junctions, "",
                                           "SWITCH_SELECTION")
    DM.CopyFeatures("junction_lyr", non10junctions)

    # Merge non10vertices with non10junctions
    DM.Merge([non10junctions, non10vertices], all_non_flag_points)  # inputs both point fc in_memory
    DM.MakeFeatureLayer(all_non_flag_points, "all_non_flag_points_lyr")

    # Tests the counts...for some reason I'm not getting stable behavior from the merge.
    mid_n = int(DM.GetCount(non10vertices).getOutput(0))
    jxn_n = int(DM.GetCount(non10junctions).getOutput(0))
    merge_n = int(DM.GetCount(all_non_flag_points).getOutput(0))
    if merge_n < mid_n + jxn_n:
        arcpy.AddWarning("The total number of flags ({0}) is less than the sum of the input junctions ({1}) "
                         "and input midpoints ({2})".format(merge_n, jxn_n, mid_n))

    # For tracing barriers, select all_non_flag_points points that intersect a 10 ha lake.
    DM.SelectLayerByLocation("all_non_flag_points_lyr", "INTERSECT", csiwaterbody_10ha, XY_TOLERANCE,
                                           "NEW_SELECTION")
    DM.CopyFeatures("all_non_flag_points_lyr", barriers)

    # Trace1-Trace downstream to first barrier (junctions+midvertices in 10 ha lake) starting from flags_10ha_lake_junctions flag points.
    DM.TraceGeometricNetwork(network, "trace1", flags_10ha_lake_junctions, "TRACE_DOWNSTREAM",
                                           barriers)

    # Save trace1 flowlines and junctions to layers on disk.
    DM.CopyFeatures("trace1\HYDRO_NET_Junctions", trace1_junctions)  # extra for debugging
    DM.CopyFeatures("trace1\NHDFlowline", trace1_flowline)

    # Select vertice midpoints that intersect trace1 flowlines selection for new flags for trace2.
    DM.MakeFeatureLayer(non10vertices, "non10vertices_lyr")
    DM.SelectLayerByLocation("non10vertices_lyr", "INTERSECT", trace1_flowline, "", "NEW_SELECTION")

    # Trace2-Trace downstream from midpoints of flowlines that intersect the selected flowlines from trace1.
    DM.TraceGeometricNetwork(network, "trace2", "non10vertices_lyr", "TRACE_DOWNSTREAM")

    # Save trace1 flowlines and junctions to layers and then shapes on disk.
    DM.CopyFeatures("trace2\HYDRO_NET_Junctions", trace2_junctions)
    DM.CopyFeatures("trace2\NHDFlowline", trace2_flowline)  # extra for debugging
    arcpy.AddMessage("Done tracing.")

    # Make shapefile for seepage lakes. (Ones that don't intersect flowlines)
    if exclude_intermit_flowlines:
        class_field_name = "LakeConnection_Permanent"
    else:
        class_field_name = "LakeConnection"
    DM.AddField(temp_fc, class_field_name, "TEXT", field_length=13)
    DM.MakeFeatureLayer(temp_fc, "out_fc_lyr")
    DM.SelectLayerByLocation("out_fc_lyr", "INTERSECT", nhdflowline, XY_TOLERANCE, "NEW_SELECTION")
    DM.SelectLayerByLocation("out_fc_lyr", "INTERSECT", nhdflowline, "", "SWITCH_SELECTION")
    DM.CalculateField("out_fc_lyr", class_field_name, """'Isolated'""", "PYTHON")

    # New type of "Isolated" classification, mostly for "permanent" but there were some oddballs in "maximum" too
    DM.SelectLayerByLocation("out_fc_lyr", "INTERSECT", startdangles, XY_TOLERANCE, "NEW_SELECTION")
    DM.SelectLayerByLocation("out_fc_lyr", "INTERSECT", enddangles, XY_TOLERANCE, "SUBSET_SELECTION")
    DM.CalculateField("out_fc_lyr", class_field_name, """'Isolated'""", "PYTHON")

    # Get headwater lakes.
    DM.SelectLayerByLocation("out_fc_lyr", "INTERSECT", startdangles, XY_TOLERANCE, "NEW_SELECTION")
    DM.SelectLayerByAttribute("out_fc_lyr", "REMOVE_FROM_SELECTION", '''"{}" = 'Isolated' '''.format(class_field_name))
    DM.CalculateField("out_fc_lyr", class_field_name, """'Headwater'""", "PYTHON")

    # Select csiwaterbody that intersect trace2junctions
    arcpy.AddMessage("Beginning connectivity attribution...")
    DM.SelectLayerByLocation("out_fc_lyr", "INTERSECT", trace2_junctions, XY_TOLERANCE, "NEW_SELECTION")
    DM.CalculateField("out_fc_lyr", class_field_name, """'DrainageLk'""", "PYTHON")

    # Get stream drainage lakes. Either unassigned so far or convert "Headwater" if a permanent stream flows into it,
    # which is detected with "non_artificial_end"
    DM.SelectLayerByAttribute("out_fc_lyr", "NEW_SELECTION", '''"{}" IS NULL'''.format(class_field_name))
    DM.CalculateField("out_fc_lyr", class_field_name, """'Drainage'""", "PYTHON")
    if exclude_intermit_flowlines:
        DM.SelectLayerByAttribute("out_fc_lyr", "NEW_SELECTION", '''"{}" = 'Headwater' '''.format(class_field_name))
        DM.SelectLayerByLocation("out_fc_lyr", "INTERSECT", non_artificial_end, XY_TOLERANCE, "SUBSET_SELECTION")
        DM.CalculateField("out_fc_lyr", class_field_name, """'Drainage'""", "PYTHON")

        # Prevent 'upgrades' due to very odd flow situations and artifacts of bad digitization. The effects of these
        # are varied--to avoid confusion, just keep the class  assigned with all flowlines

        # 1--Purely hypothetical, not seen in testing
        DM.SelectLayerByAttribute("out_fc_lyr", "NEW_SELECTION",
                                                '''"LakeConnection" = 'Isolated' AND "LakeConnection_Permanent" <> 'Isolated' ''')
        DM.CalculateField("out_fc_lyr", class_field_name, """'Isolated'""", "PYTHON")

        # 2--Headwater to Drainage upgrade seen in testing with odd multi-inlet flow situation
        DM.SelectLayerByAttribute("out_fc_lyr", "NEW_SELECTION",
                                            '''"LakeConnection" = 'Headwater' AND "LakeConnection_Permanent" IN ('Drainage', 'DrainageLk') ''')
        DM.CalculateField("out_fc_lyr", class_field_name, """'Headwater'""", "PYTHON")

        # 3--Drainage to DrainageLk upgrade seen in testing when intermittent stream segments were used
        # erroneously instead of artificial paths
        DM.SelectLayerByAttribute("out_fc_lyr", "NEW_SELECTION",
                                            '''"LakeConnection" = 'Drainage' AND "LakeConnection_Permanent" = 'DrainageLk' ''')
        DM.CalculateField("out_fc_lyr", class_field_name, """'Drainage'""", "PYTHON")
        DM.SelectLayerByAttribute("out_fc_lyr", "CLEAR_SELECTION")

        # Add change flag for users
        DM.AddField(temp_fc, "LakeConnection_Class_Fluctuates", "Text", field_length = "1")
        flag_codeblock = """def flag_calculate(arg1, arg2):
            if arg1 == arg2:
                return 'N'
            else:
                return 'Y'"""
        expression = 'flag_calculate(!LakeConnection!, !LakeConnection_Permanent!)'
        DM.CalculateField(temp_fc, "LakeConnection_Class_Fluctuates", expression, "PYTHON", flag_codeblock)

    # Project output once done with both. Switching CRS earlier causes trace problems.
    if not exclude_intermit_flowlines:
        DM.CopyFeatures(temp_fc, out_feature_class)
    else:
        DM.Project(temp_fc, out_feature_class, arcpy.SpatialReference(102039))

    # Clean up
    for item in this_tool_layers + this_tool_temp:
        if arcpy.Exists(item):
            DM.Delete(item)

    if not debug_mode:
        DM.Delete("trace1")
        DM.Delete("trace2")
    arcpy.AddMessage("{} classification is complete.".format(class_field_name))

def full_classify(nhd, out_feature_class, debug_mode = False):
    classify_lakes(nhd, out_feature_class, debug_mode = debug_mode)
    classify_lakes(nhd, out_feature_class, exclude_intermit_flowlines=True, debug_mode = debug_mode)

def main():
    nhd = arcpy.GetParameterAsText(0)
    out_feature_class = arcpy.GetParameterAsText(1)
    full_classify(nhd, out_feature_class, debug_mode = False)

if __name__ == '__main__':
    main()
