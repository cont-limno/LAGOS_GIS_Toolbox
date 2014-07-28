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


def upstream_lakes(nhd_gdb, output_table):
    nhd_waterbody = os.path.join(nhd_gdb, 'NHDWaterbody')
    nhd_flowline = os.path.join(nhd_gdb, 'NHDFlowline')
    junctions = os.path.join(nhd_gdb, 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhd_gdb, 'HYDRO_NET')

    arcpy.env.workspace = 'in_memory'

    fcodes = (39000, 39004, 39009, 39010, 39011, 39012, 43600, 43613, 43615, 43617, 43618, 43619, 43621)
    gte_4ha_lakes_query = '''("AreaSqKm" >=0.04 AND "FCode" IN %s) OR ("FCode" = 43601 AND "AreaSqKm" >= 0.1)''' % (fcodes,)
    gte_10ha_lakes_query = '''("AreaSqKm" >=0.1 AND "FCode" IN %s) OR ("FCode" = 43601 AND "AreaSqKm" >= 0.1)''' % (fcodes,)

    arcpy.Select_analysis(nhd_waterbody, 'gte_4ha_lakes', gte_4ha_lakes_query)
    arcpy.Select_analysis(nhd_waterbody, 'gte_10ha_lakes', gte_10ha_lakes_query)
    arcpy.CopyRows_management('gte_4ha_lakes', 'output_table')

    count_fields = ['4ha_Upstream_Lakes_Count', '10ha_Upstream_Lakes_Count']
    area_fields = ['4ha_Upstream_Lakes_Area', '10ha_Upstream_Lakes_Area']
    for cf in count_fields:
        arcpy.AddField_management('output_table', count_field, 'LONG')
    for af in area_fields:
        arcpy.AddField_management('output_table', count_field, 'DOUBLE')
    new_fields= count_fields + area_fields

    with arcpy.da.UpdateCursor('output_table', ['Permanent_Identifier'] + new_fields) as cursor:
            for row in cursor:
                id = row[0]
                cu.multi_msg("Tracing upstream network for lake ID {0}".format(id))
                where_clause = """"{0}" = '{1}'""".format('Permanent_Identifier', id)
                arcpy.MakeFeatureLayer_management('gte_4ha_lakes', "this_lake",
                                                    where_clause)
                arcpy.SelectLayerByLocation_management("junctions", "INTERSECT",
                                                "this_lake", search_distance = "1m")
                arcpy.CopyFeatures_management("junctions", 'this_lake_jxns')
                arcpy.TraceGeometricNetwork_management(hydro_net, "upstream",
                                    'this_lake_jxns', "TRACE_UPSTREAM")
                arcpy.SelectLayerByLocation_management('gte_4ha_lakes', "INTERSECT",
                                    "upstream/NHDFlowline", '1m', 'NEW_SELECTION')
                # have to do this because empty selection is possible
                arcpy.CopyFeatures_management
                # row[1] is 4ha_Upstream_Lakes_Count
                # row [3] is 4ha_Upstream_Lakes_Area
                row[1] = int(arcpy.GetCount_management('gte_4ha_lakes').getOutput(0))
                total_area = 0
                with arcpy.da.SearchCursor('gte_4ha_lakes', ['AreaSqKm']) as cursor:
                    for row in cursor:
                        total_area += row[0]
                row[3] = total_area

                # same but for 10ha
                arcpy.SelectLayerByLocation_management('gte_10ha_lakes', "INTERSECT",
                                    "upstream/NHDFlowline", '1m', 'NEW_SELECTION')
                row[2] = int(arcpy.GetCount_management('gte_10ha_lakes').getOutput(0))
                total_area = 0
                with arcpy.da.SearchCursor('gte_4ha_lakes', ['AreaSqKm']) as cursor:
                    for row in cursor:
                        total_area += row[0]
                row[4] = total_area

                cursor.updateRow(row)

                for item in ['this_lake', 'this_lake_jxns', 'upstream']:
                    arcpy.Delete_management(item)

    all_fields = [f.name for f in arcpy.ListFields('output_table')]
    for f in all_fields:
        if f not in ['Permanent_Identifier'] + new_fields:
            try:
                arcpy.DeleteField_management('output_table', f)
            except:
                continue

    arcpy.CopyRows_management('output_table', output_table)
    for item in ['gte_10ha_lakes', 'gte_10ha_lakes', 'output_table']:
        arcpy.Delete_management(item)

def main():
    pass

if __name__ == '__main__':
    main()
