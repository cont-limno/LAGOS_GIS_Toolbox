# Filename : LakeClass.py
# Author : Scott Stopyak, Geographer, Michigan State University
# Purpose : Classify lakes according to their connectivity to the hydrologic network using only NHD as input.
# Modified: Nicole Smith, 2017

import os
import arcpy
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

    layers_list = []
    temp_feature_class = "in_memory/temp_fc"

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
        arcpy.CopyFeatures_management(out_feature_class, temp_feature_class)
    else:
        arcpy.Select_analysis(nhdwaterbody, temp_feature_class, all_lakes_reservoirs_filter)


    # Get lakes, ponds and reservoirs over 10 hectares.
    lakes_10ha_filter = '''"AreaSqKm" >= 0.1 AND "FType" IN (390, 436)'''
    arcpy.Select_analysis(nhdwaterbody, "csiwaterbody_10ha", lakes_10ha_filter)

    # Exclude intermittent flowlines, if requested
    if exclude_intermit_flowlines:
        flowline_where_clause = '''"FCode" NOT IN (46003,46007)'''
        nhdflowline = arcpy.Select_analysis(nhdflowline, "nhdflowline_filtered", flowline_where_clause)

    # Make dangle points at end of nhdflowline
    arcpy.FeatureVerticesToPoints_management(nhdflowline, "dangles", "DANGLE")
    layers_list.append(arcpy.MakeFeatureLayer_management("dangles", "dangles_lyr"))

    # Isolate start dangles from end dangles.
    arcpy.FeatureVerticesToPoints_management(nhdflowline, "start", "START")
    arcpy.FeatureVerticesToPoints_management(nhdflowline, "end", "END")

    arcpy.SelectLayerByLocation_management("dangles_lyr", "ARE_IDENTICAL_TO", "start")
    arcpy.CopyFeatures_management("dangles_lyr", "startdangles")
    arcpy.SelectLayerByLocation_management("dangles_lyr", "ARE_IDENTICAL_TO", "end")
    arcpy.CopyFeatures_management("dangles_lyr", "enddangles")

    # Special handling for lakes that have some intermittent flow in and some permanent
    if  exclude_intermit_flowlines:
        layers_list.append(arcpy.MakeFeatureLayer_management(nhdflowline, "nhdflowline_lyr"))
        arcpy.SelectLayerByAttribute_management("nhdflowline_lyr", "NEW_SELECTION", '''"WBArea_Permanent_Identifier" is null''')
        arcpy.FeatureVerticesToPoints_management("nhdflowline_lyr", "non_artificial_end", "END")
        arcpy.SelectLayerByAttribute_management("nhdflowline_lyr", "CLEAR_SELECTION")

    arcpy.AddMessage("Found source area nodes.")

    # Get junctions from lakes >= 10 hectares.
    layers_list.append(arcpy.MakeFeatureLayer_management(nhdjunction, "junction_lyr"))
    arcpy.SelectLayerByLocation_management("junction_lyr", "INTERSECT", "csiwaterbody_10ha", XY_TOLERANCE,
                                           "NEW_SELECTION")

    arcpy.CopyFeatures_management("junction_lyr", "flags_10ha_lake_junctions")
    arcpy.AddMessage("Found lakes >= 10 ha.")

    # Make points shapefile and layer at flowline vertices to act as potential flags and/or barriers.
    arcpy.AddMessage("Tracing...")
    arcpy.FeatureVerticesToPoints_management(nhdflowline, "midvertices", "MID")
    layers_list.append(arcpy.MakeFeatureLayer_management("midvertices", "midvertices_lyr"))

    # Get vertices that are not coincident with 10 hectare lake junctions.
    arcpy.SelectLayerByLocation_management("midvertices_lyr", "INTERSECT", "flags_10ha_lake_junctions", "",
                                           "NEW_SELECTION")
    arcpy.SelectLayerByLocation_management("midvertices_lyr", "INTERSECT", "flags_10ha_lake_junctions", "",
                                           "SWITCH_SELECTION")
    arcpy.CopyFeatures_management("midvertices_lyr", "non10vertices")

    # Get junctions that are not coincident with 10 hectare lake junctions.
    arcpy.SelectLayerByLocation_management("junction_lyr", "INTERSECT", "flags_10ha_lake_junctions", "",
                                           "NEW_SELECTION")
    arcpy.SelectLayerByLocation_management("junction_lyr", "INTERSECT", "flags_10ha_lake_junctions", "",
                                           "SWITCH_SELECTION")
    arcpy.CopyFeatures_management("junction_lyr", "non10junctions")

    # Merge non10vertices with non10junctions
    arcpy.Merge_management(["non10junctions", "non10vertices"], "all_non_flag_points")  # inputs both point fc in_memory
    layers_list.append(arcpy.MakeFeatureLayer_management("all_non_flag_points", "all_non_flag_points_lyr"))

    # Tests the counts...for some reason I'm not getting stable behavior from the merge.
    mid_n = int(arcpy.GetCount_management("non10vertices").getOutput(0))
    jxn_n = int(arcpy.GetCount_management("non10junctions").getOutput(0))
    merge_n = int(arcpy.GetCount_management("all_non_flag_points").getOutput(0))
    if merge_n < mid_n + jxn_n:
        arcpy.AddWarning("The total number of flags ({0}) is less than the sum of the input junctions ({1}) "
                         "and input midpoints ({2})".format(merge_n, jxn_n, mid_n))

    # For tracing barriers, select all_non_flag_points points that intersect a 10 ha lake.
    arcpy.SelectLayerByLocation_management("all_non_flag_points_lyr", "INTERSECT", "csiwaterbody_10ha", XY_TOLERANCE,
                                           "NEW_SELECTION")
    arcpy.CopyFeatures_management("all_non_flag_points_lyr", "barriers")

    # Trace1-Trace downstream to first barrier (junctions+midvertices in 10 ha lake) starting from flags_10ha_lake_junctions flag points.
    arcpy.TraceGeometricNetwork_management(network, "trace1", "flags_10ha_lake_junctions", "TRACE_DOWNSTREAM",
                                           "barriers")

    # Save trace1 flowlines and junctions to layers on disk.
    arcpy.CopyFeatures_management("trace1\HYDRO_NET_Junctions", "trace1_junctions")  # extra for debugging
    arcpy.CopyFeatures_management("trace1\NHDFlowline", "trace1_flowline")

    # Select vertice midpoints that intersect trace1 flowlines selection for new flags for trace2.
    layers_list.append(arcpy.MakeFeatureLayer_management("non10vertices", "non10vertices_lyr"))
    arcpy.SelectLayerByLocation_management("non10vertices_lyr", "INTERSECT", "trace1_flowline", "", "NEW_SELECTION")

    # Trace2-Trace downstream from midpoints of flowlines that intersect the selected flowlines from trace1.
    arcpy.TraceGeometricNetwork_management(network, "trace2", "non10vertices_lyr", "TRACE_DOWNSTREAM")

    # Save trace1 flowlines and junctions to layers and then shapes on disk.
    arcpy.CopyFeatures_management("trace2\HYDRO_NET_Junctions", "trace2junctions")
    arcpy.CopyFeatures_management("trace2\NHDFlowline", "trace2_flowline")  # extra for debugging
    arcpy.AddMessage("Done tracing.")

    # Make shapefile for seepage lakes. (Ones that don't intersect flowlines)
    if exclude_intermit_flowlines:
        class_field_name = "LakeConnectivity_Permanent"
    else:
        class_field_name = "LakeConnectivity"
    arcpy.AddField_management(temp_feature_class, class_field_name, "TEXT", field_length=13)
    layers_list.append(arcpy.MakeFeatureLayer_management(temp_feature_class, "out_fc_lyr"))
    arcpy.SelectLayerByLocation_management("out_fc_lyr", "INTERSECT", nhdflowline, XY_TOLERANCE, "NEW_SELECTION")
    arcpy.SelectLayerByLocation_management("out_fc_lyr", "INTERSECT", nhdflowline, "", "SWITCH_SELECTION")
    arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'Isolated'""", "PYTHON")

    # New type of "Isolated" classification, mostly for "permanent" but there were some oddballs in "maximum" too
    arcpy.SelectLayerByLocation_management("out_fc_lyr", "INTERSECT", "startdangles", XY_TOLERANCE, "NEW_SELECTION")
    arcpy.SelectLayerByLocation_management("out_fc_lyr", "INTERSECT", "enddangles", XY_TOLERANCE, "SUBSET_SELECTION")
    arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'Isolated'""", "PYTHON")

    # Get headwater lakes.
    arcpy.SelectLayerByLocation_management("out_fc_lyr", "INTERSECT", "startdangles", XY_TOLERANCE, "NEW_SELECTION")
    arcpy.SelectLayerByAttribute_management("out_fc_lyr", "REMOVE_FROM_SELECTION", '''"{}" = 'Isolated' '''.format(class_field_name))
    arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'Headwater'""", "PYTHON")

    # Select csiwaterbody that intersect trace2junctions
    arcpy.AddMessage("Beginning connectivity attribution...")
    arcpy.SelectLayerByLocation_management("out_fc_lyr", "INTERSECT", "trace2junctions", XY_TOLERANCE, "NEW_SELECTION")
    arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'DR_LakeStream'""", "PYTHON")

    # Get stream drainage lakes. Either unassigned so far or convert "Headwater" if a permanent stream flows into it,
    # which is detected with "non_artificial_end"
    arcpy.SelectLayerByAttribute_management("out_fc_lyr", "NEW_SELECTION", '''"{}" IS NULL'''.format(class_field_name))
    arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'DR_Stream'""", "PYTHON")
    if exclude_intermit_flowlines:
        arcpy.SelectLayerByAttribute_management("out_fc_lyr", "NEW_SELECTION", '''"{}" = 'Headwater' '''.format(class_field_name))
        arcpy.SelectLayerByLocation_management("out_fc_lyr", "INTERSECT", "non_artificial_end", XY_TOLERANCE, "SUBSET_SELECTION")
        arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'DR_Stream'""", "PYTHON")

        # Prevent 'upgrades' due to very odd flow situations and artifacts of bad digitization. The effects of these
        # are varied--to avoid confusion, just keep the class  assigned with all flowlines

        # 1--Purely hypothetical, not seen in testing
        arcpy.SelectLayerByAttribute_management("out_fc_lyr", "NEW_SELECTION",
                                                '''"LakeConnectivity" = 'Isolated' AND "LakeConnectivity_Permanent" <> 'Isolated' ''')
        arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'Isolated'""", "PYTHON")

        # 2--Headwater to DR_Stream upgrade seen in testing with odd multi-inlet flow situation
        arcpy.SelectLayerByAttribute_management("out_fc_lyr", "NEW_SELECTION",
                                            '''"LakeConnectivity" = 'Headwater' AND "LakeConnectivity_Permanent" IN ('DR_Stream', 'DR_LakeStream') ''')
        arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'Headwater'""", "PYTHON")

        # 3--DR_Stream to DR_LakeStream upgrade seen in testing when intermittent stream segments were used
        # erroneously instead of artificial paths
        arcpy.SelectLayerByAttribute_management("out_fc_lyr", "NEW_SELECTION",
                                            '''"LakeConnectivity" = 'DR_Stream' AND "LakeConnectivity_Permanent" = 'DR_LakeStream' ''')
        arcpy.CalculateField_management("out_fc_lyr", class_field_name, """'DR_Stream'""", "PYTHON")
        arcpy.SelectLayerByAttribute_management("out_fc_lyr", "CLEAR_SELECTION")

        # Add change flag for users
        arcpy.AddField_management(temp_feature_class, "Has_Only_Permanent_Connectivity", "Text", field_length = "1")
        flag_codeblock = """def flag_calculate(arg1, arg2):
            if arg1 == arg2:
                return 'Y'
            else:
                return 'N'"""
        expression = 'flag_calculate(!LakeConnectivity!, !LakeConnectivity_Permanent!)'
        arcpy.CalculateField_management(temp_feature_class, "ChangeFlag", expression, "PYTHON", flag_codeblock)



    # Project output once done with both. Switching CRS earlier causes trace problems.
    if not exclude_intermit_flowlines:
        arcpy.CopyFeatures_management(temp_feature_class, out_feature_class)
    else:
        arcpy.Project_management(temp_feature_class, out_feature_class, arcpy.SpatialReference(102039))


    # Clean up
    for layer in layers_list:
        arcpy.Delete_management(layer)
    else:
        arcpy.Delete_management("in_memory")
    arcpy.AddMessage("{} classification is complete.".format(class_field_name))

def full_classify(nhd, out_feature_class):
    classify_lakes(nhd, out_feature_class)
    classify_lakes(nhd, out_feature_class, exclude_intermit_flowlines=True)

def main():
    nhd = arcpy.GetParameterAsText(0)
    out_feature_class = arcpy.GetParameterAsText(1)
    full_classify(nhd, out_feature_class)

def test(out_feature_class):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_data_gdb = os.path.abspath(os.path.join(os.pardir, 'TestData_0411.gdb'))
    nhd = test_data_gdb
    out_feature_class = out_feature_class
    full_classify(nhd, out_feature_class)

if __name__ == '__main__':
    main()
