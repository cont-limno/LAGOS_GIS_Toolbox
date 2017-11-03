#-------------------------------------------------------------------------------
# Name:        upstream_lakes
# Purpose:
#
# Author:      smithn78
#
# Created:     16/07/2014

# Tool steps summary
# 1)	Identify necessary items in the NHD geodatabase and set environments
# 2)	Create layer of lakes greater than 4ha and layer of lakes greater than 10ha
# 3)	Add the new count and area fields to the output table
# 4)	Using a search cursor, for each lake:
#     a.	Make a layer containing only this lake
#     b.	Select junctions (points at each hydrological connection) within 1m of this lake
#     c.	If the number of junctions is 0, there is no upstream network at all. Enter 0s in all the output fields.
#     d.	If the number of junctions is at least 1:
#         i.	Trace the geometric network upstream of the junction(s) for this lake
#        ii.	Select lakes that intersect the flowlines in the trace (these are the upstream lakes
#       iii.	If there are no lakes in the upstream network, enter 0s in the output fields.
#       iv.	If there are lakes in the upstream network,
#           1.	Create a layer of the 4ha lakes, count them, and using a search cursor, sum their area. Update the output fields with these values.
#           2.	Create a layer of the 10ha lakes, count them, and using a search cursor, sum their area. Update the output fields with these values.
# 5)	Remove unnecessary fields from the output table
# 6)	Clean up intermediates

#-------------------------------------------------------------------------------
import os
import arcpy
import csiutils as cu

def upstream_lakes(nhd_gdb, output_table, unique_id = 'lagoslakeid'):
    #define paths in nhd geodatabase
    nhd_waterbody = os.path.join(nhd_gdb, 'NHDWaterbody')
    nhd_junctions = os.path.join(nhd_gdb, 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET')

    arcpy.env.workspace = 'in_memory'

    arcpy.AddMessage('Preparing layers and fields for calculations....')
    arcpy.MakeFeatureLayer_management(nhd_junctions, 'junctions')


    # select only lakes as defined in our project: waterbodies with one of these
    # types and greater than 4ha, and certain reservoirs greater than 10ha
    # These filters should be aligned with LakeConnectivity (they currently are)
    gte_1ha_lakes_query = ''' "AreaSqKm" >=0.009 AND "FType" IN (390, 436) '''
    gte_4ha_lakes_query = ''' "AreaSqKm" >=0.04 AND "FType" IN (390, 436) '''
    gte_10ha_lakes_query = ''' "AreaSqKm" >=0.1 AND "FType" IN (390, 436) '''

    arcpy.MakeFeatureLayer_management(nhd_waterbody, 'gte_4ha_lakes', gte_4ha_lakes_query)
    arcpy.MakeFeatureLayer_management(nhd_waterbody, 'gte_10ha_lakes', gte_10ha_lakes_query)
    arcpy.MakeFeatureLayer_management(nhd_waterbody, 'gte_1ha_lakes', gte_1ha_lakes_query)
    arcpy.CopyRows_management('gte_1ha_lakes', 'output_table')

    # (need this for line 61 make feature layer to work right!)
    arcpy.CopyFeatures_management('gte_1ha_lakes', 'gte_1ha_lakes_DISK')

    # add the new fields we'll calculate: count and area
    count_fields = ['Upstream_Lakes_4ha_Count', 'Upstream_Lakes_10ha_Count']
    area_fields = ['Upstream_Lakes_4ha_Area_ha', 'Upstream_Lakes_10ha_Area_ha']
    for cf in count_fields:
        arcpy.AddField_management('output_table', cf, 'LONG')
    for af in area_fields:
        arcpy.AddField_management('output_table', af, 'DOUBLE')
    new_fields= count_fields + area_fields

    # for each lake, use its junctions as input flags to the upstream trace, then
    # evalute the traced network for how many lakes are in it
    arcpy.AddMessage("Calculating upstream network for each lake. Depending on the network, this may take up to a few hours...")
    with arcpy.da.UpdateCursor('output_table', [unique_id] + new_fields) as cursor:
        for row in cursor:
            id = row[0]

            # get the junction points on top of this lake, can be 0 or several
            # TODO: Make this flexible based on whether ID is string or integer
            where_clause = """"{0}" = {1}""".format(unique_id, id)
            arcpy.MakeFeatureLayer_management('gte_1ha_lakes_DISK', "this_lake",
                                                where_clause)
            arcpy.SelectLayerByLocation_management('junctions', "INTERSECT",
                                            "this_lake", "1 Meters")
            count_jxns = int(arcpy.GetCount_management('junctions').getOutput(0))

            # if the lake has no upstream connectivity whatsoever, it will have
            # no junctions on top of it. assign 0s
            # to the counts of upstream lakes. This can either be an "isolated"
            # lake or a "headwater" lake
            if count_jxns <= 0:
                row[1:] = [0, 0, 0, 0]

            # if there are any junctions, go ahead and trace upstream
            else:
                arcpy.CopyFeatures_management("junctions", 'this_lake_jxns')
                arcpy.TraceGeometricNetwork_management(hydro_net, "upstream",
                                    'this_lake_jxns', "TRACE_UPSTREAM")
                arcpy.SelectLayerByLocation_management('gte_4ha_lakes', "INTERSECT",
                                    "upstream/NHDFlowline", '1 Meters', 'NEW_SELECTION')
                # Remove this lake from the selection!!
                arcpy.SelectLayerByAttribute_management('gte_4ha_lakes',
                                    'REMOVE_FROM_SELECTION', where_clause)
                count_4ha_lakes = int(arcpy.GetCount_management('gte_4ha_lakes').getOutput(0))

                # if there is upstream connectivity but no countable lakes
                # assign 0s for all the counts/areas and do not try to copy rows
                if count_4ha_lakes <= 0:
                    row[1:] = [0, 0, 0, 0]

                # if there are any lakes upstream, copy rows before doing
                # counts so we can use a search cursor on just these lakes
                else:
                    arcpy.CopyRows_management('gte_4ha_lakes', 'these_4ha_lakes')

                    # row[1] is 4ha_Upstream_Lakes_Count
                    # row [3] is 4ha_Upstream_Lakes_Area
                    row[1] = int(arcpy.GetCount_management('these_4ha_lakes').getOutput(0))
                    total_area = 0
                    with arcpy.da.SearchCursor('these_4ha_lakes', ['AreaSqKm']) as area4_cursor:
                        for area4_row in area4_cursor:
                            total_area += area4_row[0] * 100
                    row[3] = total_area

                    # same but for 10ha
                    arcpy.SelectLayerByLocation_management('gte_10ha_lakes', "INTERSECT",
                                        "upstream/NHDFlowline", '1 Meters', 'NEW_SELECTION')
                    arcpy.SelectLayerByAttribute_management('gte_10ha_lakes',
                                    'REMOVE_FROM_SELECTION', where_clause)
                    count_10ha_lakes = int(arcpy.GetCount_management('gte_10ha_lakes').getOutput(0))

                    # don't try to copy rows if selection is empty
                    if count_10ha_lakes <= 0:
                        row[2] = 0
                        row[4] = 0
                    # if there are features selected, copy rows so we
                    # can use a search cursor
                    else:
                        arcpy.CopyRows_management('gte_10ha_lakes', 'these_10ha_lakes')
                        row[2] = int(arcpy.GetCount_management('these_10ha_lakes').getOutput(0))
                        total_area = 0
                        with arcpy.da.SearchCursor('these_4ha_lakes', ['AreaSqKm']) as area10_cursor:
                            for area10_row in area10_cursor:
                                total_area += area10_row[0] * 100
                        row[4] = total_area
            cursor.updateRow(row)

            # delete intermediates before next iteration
            for item in ['this_lake', 'this_lake_jxns', 'upstream', 'these_4ha_lakes', 'these_10ha_lakes']:
                    try:
                        arcpy.Delete_management(item)
                    except:
                        continue

    # clean up the output table
    all_fields = [f.name for f in arcpy.ListFields('output_table')]
    for f in all_fields:
        if f not in [unique_id] + new_fields:
            try:
                arcpy.DeleteField_management('output_table', f)
            except:
                continue

    # write out the final file and clean up intermediates
    arcpy.CopyRows_management('output_table', output_table)
    for item in ['junctions', 'gte_4ha_lakes', 'gte_10ha_lakes', 'gte_1ha_lakes', 'output_table', 'in_memory']:
        arcpy.Delete_management(item)

def main():
    nhd_gdb = arcpy.GetParameterAsText(0)
    output_table = arcpy.GetParameterAsText(1)
    upstream_lakes(nhd_gdb, output_table)

def test(out_table):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    test_data_gdb = os.path.abspath(os.path.join(os.pardir, 'TestData_0411.gdb'))
    nhd = test_data_gdb
    out_table = out_table
    upstream_lakes(nhd, out_table)

if __name__ == '__main__':
    main()
