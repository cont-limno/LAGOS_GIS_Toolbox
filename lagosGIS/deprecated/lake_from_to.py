# filename: lake_from_to.py
# author: Nicole J Smith
# version: 2.0 Beta
# LAGOS module(s): CONN
# tool type: re-usable (not ArcGIS Toolbox)
# status: This code was a PROTOTYPE and was replaced with alternate Python code for the CONN database. It produces
# a very similar result with differences in complicated flow situations.

import os
import arcpy
from arcpy import management as DM

LAGOS_LAKE_FILTER = "AreaSqKm >= .01 AND FCode IN (39000,39004,39009,39010,39011,39012,43600,43613,43615,43617,43618,43619,43621)"

def lake_from_to(nhd_subregion_gdb, output_table):
    """
    Produce a flow table with a row for each lake that flows into another lake. The complexity of the network is
    simplified to show only which lakes are upstream or downstream of other lakes.
    :param nhd_subregion_gdb: The NHD HR subregion to summarize
    :param output_table: The output table to save the results to.
    :return:
    """

    arcpy.env.workspace = 'in_memory'
    waterbody0 = os.path.join(nhd_subregion_gdb, 'NHDWaterbody')
    network = os.path.join(nhd_subregion_gdb, 'Hydrography','HYDRO_NET')
    junctions0 = os.path.join(nhd_subregion_gdb, 'HYDRO_NET_Junctions')

    # use layers for selections. We will only work with lakes over 1 hectare for this tool.
    waterbody = DM.MakeFeatureLayer(waterbody0, 'waterbody', where_clause = LAGOS_LAKE_FILTER)
    num_wbs = int(arcpy.GetCount_management(waterbody).getOutput(0))
    junctions = DM.MakeFeatureLayer(junctions0, 'junctions')

    DM.SelectLayerByLocation(junctions, 'INTERSECT', waterbody, '1 Meters', 'NEW_SELECTION')
    junctions_1ha = DM.MakeFeatureLayer(junctions, 'junctions_1ha')

    # insert results into output table
    DM.CreateTable(os.path.dirname(output_table), os.path.basename(output_table))
    DM.AddField(output_table, 'FROM_PERMANENT_ID', 'TEXT', field_length = 40)
    DM.AddField(output_table, 'TO_PERMANENT_ID', 'TEXT', field_length = 40)

    # create a dictionary to hold results in memory
    results = []

    counter = 0
    progress = .01
    arcpy.AddMessage("Starting network tracing...")
    with arcpy.da.SearchCursor(waterbody, 'Permanent_Identifier') as cursor:
        for row in cursor:
            # set up a progress printer
            counter += 1
            if counter >= float(num_wbs)*progress:
                progress += .01
                arcpy.AddMessage("{}% complete...".format(round(progress*100), 1))

            # select this lake
            id = row[0]
            where_clause = """"{0}" = '{1}'""".format('Permanent_Identifier', id)
            this_waterbody = DM.MakeFeatureLayer(waterbody, 'this_waterbody', where_clause)

            # select junctions overlapping this lake. only the downstream one matters, rest have no effect
            DM.SelectLayerByLocation(junctions_1ha, 'INTERSECT', this_waterbody, '1 Meters')
            count_junctions = int(arcpy.GetCount_management(junctions_1ha).getOutput(0))
            if count_junctions == 0:
                # add a row with no "TO" lake to the results
                results.append({'FROM': id, 'TO': None})
            else:
                # copy with selection on
                this_junctions = DM.MakeFeatureLayer(junctions_1ha, 'this_junctions')
                DM.TraceGeometricNetwork(network, 'downstream', this_junctions, 'TRACE_DOWNSTREAM')
                # select lakes that intersect the downstream network with a tolerance of 1 meters
                DM.SelectLayerByLocation(waterbody, 'INTERSECT', 'downstream/NHDFlowline', '1 Meters', 'NEW_SELECTION')
                # remove this lake
                DM.SelectLayerByAttribute(waterbody, 'REMOVE_FROM_SELECTION', where_clause)
                # get the count, if it's 0 then there should be no table entry or something?
                count_waterbody = int(arcpy.GetCount_management(waterbody).getOutput(0))
                # copy those into the table that you're storing stuff in
                if count_waterbody == 0:
                    # add a row with no "TO" lake to the results
                    results.append({'FROM': id, 'TO': None})
                else:
                    # for each ID, how am I getting those
                    to_ids = [row[0] for row in arcpy.da.SearchCursor(waterbody, 'Permanent_Identifier')]
                    for to_id in to_ids:
                        result = {'FROM': id, 'TO': to_id}
                        results.append(result)

                # delete all the intermediates
            DM.SelectLayerByAttribute(waterbody, 'CLEAR_SELECTION')
            for item in [this_waterbody, this_junctions, 'downstream']:
                DM.Delete(item)


    # insert the results in the table
    insert_cursor = arcpy.da.InsertCursor(output_table, ['FROM_PERMANENT_ID', 'TO_PERMANENT_ID'])
    for result in results:
        insert_cursor.insertRow([result['FROM'], result['TO']])

    # delete everything
    for item in [waterbody, junctions, junctions_1ha, 'in_memory']:
        DM.Delete(item)
    arcpy.AddMessage("Completed.")

def main():
    nhd_subregion_gdb = arcpy.GetParameterAsText(0)
    output_table = arcpy.GetParameterAsText(1)
    lake_from_to(nhd_subregion_gdb, output_table)

if __name__ == '__main__':
    main()
