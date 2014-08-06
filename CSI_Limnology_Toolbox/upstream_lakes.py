#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      smithn78
#
# Created:     16/07/2014
# Copyright:   (c) smithn78 2014
# Licence:     <your licence>
#-------------------------------------------------------------------------------
import os
import arcpy
import csiutils as cu


def upstream_lakes(nhd_gdb, output_table):
    #define paths in nhd geodatabase
    nhd_waterbody = os.path.join(nhd_gdb, 'NHDWaterbody')
    nhd_flowline = os.path.join(nhd_gdb, 'NHDFlowline')
    nhd_junctions = os.path.join(nhd_gdb, 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET')

    arcpy.env.workspace = 'in_memory'
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)

    arcpy.MakeFeatureLayer_management(nhd_junctions, 'junctions')

    cu.multi_msg('Preparing layers and fields for calculations....')

    # select only lakes as defined in our project, greater than 4ha, and greater
    # than 10ha
    fcodes = (39000, 39004, 39009, 39010, 39011, 39012, 43600, 43613, 43615, 43617, 43618, 43619, 43621)
    gte_4ha_lakes_query = '''("AreaSqKm" >=0.04 AND "FCode" IN %s) OR ("FCode" = 43601 AND "AreaSqKm" >= 0.1)''' % (fcodes,)
    gte_10ha_lakes_query = '''("AreaSqKm" >=0.1 AND "FCode" IN %s) OR ("FCode" = 43601 AND "AreaSqKm" >= 0.1)''' % (fcodes,)

    arcpy.MakeFeatureLayer_management(nhd_waterbody, 'gte_4ha_lakes', gte_4ha_lakes_query)
    arcpy.MakeFeatureLayer_management(nhd_waterbody, 'gte_10ha_lakes', gte_10ha_lakes_query)
    arcpy.CopyRows_management('gte_4ha_lakes', 'output_table')

    # need this for line 61 make feature layer to work right!
    arcpy.CopyFeatures_management('gte_4ha_lakes', 'gte_4ha_lakes_DISK')

    # add the new fields we'll calculate
    count_fields = ['Upstream_Lakes_4ha_Count', 'Upstream_Lakes_10ha_Count']
    area_fields = ['Upstream_Lakes_4ha_Area_ha', 'Upstream_Lakes_10ha_Area_ha']
    for cf in count_fields:
        arcpy.AddField_management('output_table', cf, 'LONG')
    for af in area_fields:
        arcpy.AddField_management('output_table', af, 'DOUBLE')
    new_fields= count_fields + area_fields

    # for each lake, use its junctions as input flags to the upstream trace, then
    # evalute the traced network for how many lakes are in it
    with arcpy.da.UpdateCursor('output_table', ['Permanent_Identifier'] + new_fields) as cursor:
        for row in cursor:
            id = row[0]
            cu.multi_msg('Calculating values for lake ID {0}'.format(id))
            # get the junction points on top of this lake, can be 0 or several
            cu.multi_msg("Tracing upstream network for lake ID {0}".format(id))
            where_clause = """"{0}" = '{1}'""".format('Permanent_Identifier', id)
            print(where_clause)
            arcpy.MakeFeatureLayer_management('gte_4ha_lakes_DISK', "this_lake",
                                                where_clause)
            print(arcpy.GetCount_management('this_lake').getOutput(0))
            arcpy.SelectLayerByLocation_management('junctions', "INTERSECT",
                                            "this_lake", "1 Meters")
            count_jxns = int(arcpy.GetCount_management('junctions').getOutput(0))
            print('count_jxns = {0}'.format(count_jxns))

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
                print('count_4ha_lakes = {0}'.format(count_4ha_lakes))

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
                    print('total_area = {0}'.format(total_area))
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
            print(row)
            cursor.updateRow(row)

            for item in ['this_lake', 'this_lake_jxns', 'upstream', 'these_4ha_lakes', 'these_10ha_lakes']:
                    try:
                        arcpy.Delete_management(item)
                    except:
                        continue

    all_fields = [f.name for f in arcpy.ListFields('output_table')]
    for f in all_fields:
        if f not in ['Permanent_Identifier'] + new_fields:
            try:
                arcpy.DeleteField_management('output_table', f)
            except:
                continue

    arcpy.CopyRows_management('output_table', output_table)
    for item in ['junctions', 'gte_4ha_lakes', 'gte_10ha_lakes', 'output_table']:
        arcpy.Delete_management(item)

def main():
    nhd_gdb = arcpy.GetParameterAsText(0)
    output_table = arcpy.GetParameterAsText(1)
    upstream_lakes(nhd_gdb, output_table)

def test():
    nhd_gdb = 'E:/RawNHD_byHUC/NHDH0411.gdb'
    output_table = 'C:/GISData/Scratch/Scratch.gdb/test_upstream_lakes'
    upstream_lakes(nhd_gdb, output_table)

if __name__ == '__main__':
    main()
