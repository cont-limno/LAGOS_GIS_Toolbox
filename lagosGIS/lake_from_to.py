import os
import arcpy
from arcpy import management as DM

def lake_from_to(nhd_subregion_gdb, output_table):
    arcpy.env.workspace = 'in_memory'
    waterbody0 = os.path.join(nhd_subregion_gdb, 'NHDWaterbody')
    network = os.path.join(nhd_subregion_gdb, 'Hydrography','HYDRO_NET')
    junctions0 = os.path.join(nhd_subregion_gdb, 'HYDRO_NET_Junctions')

    # use layers for selections
    waterbody = DM.MakeFeatureLayer(waterbody0, 'waterbody')
    junctions = DM.MakeFeatureLayer(junctions0, 'junctions')

 # create a dictionary to hold results in memory
    results = []

    with arcpy.da.SearchCursor(waterbody, 'Permanent_Identifier') as cursor:
        for row in cursor:
            id = row[0]
            where_clause = """"{0}" = '{1}'""".format('Permanent_Identifier', id)
            print where_clause
            this_waterbody = DM.MakeFeatureLayer(waterbody0, 'this_waterbody', where_clause)
            DM.SelectLayerByLocation(junctions, 'INTERSECT', this_waterbody, '1 Meters')
            count_junctions = int(arcpy.GetCount_management(junctions).getOutput(0))
            print count_junctions
            if count_junctions == 0:
                # add a row with no "TO" lake to the results
                results.append({'FROM': id, 'TO': None})
            else:
                # copy with selection on
                this_junctions = DM.CopyFeatures(junctions, 'this_junctions')
                DM.TraceGeometricNetwork(network, 'downstream', this_junctions, 'TRACE_DOWNSTREAM')
                # select lakes that intersect the downstream network with a tolerance of 1 meters
                DM.SelectLayerByLocation(waterbody, 'INTERSECT', 'downstream/NHDFlowline', '1 Meters', 'NEW_SELECTION')
                # remove this lake now or later?
                DM.SelectLayerByAttribute(waterbody, 'REMOVE_FROM_SELECTION', where_clause)
                # get the count, if it's 0 then there should be no table entry or something?
                count_waterbody = int(arcpy.GetCount_management(waterbody).getOutput(0))
                print count_waterbody
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
                        print result

                # delete all the intermediates
                for item in [this_waterbody, this_junctions, 'downstream']:
                    DM.Delete(item)

    # insert results into output table
    DM.CreateTable(output_table)
    DM.AddField(output_table, 'FROM', 'TEXT', field_length = 40)
    DM.AddField(output_table, 'TO', 'TEXT', field_length = 40)
    insert_cursor = arcpy.da.InsertCursor(output_table, ['FROM', 'TO'])
    for result in results:
        insert_cursor.insertRow(result['FROM'], result['TO'])

    # delete everything
    for item in [waterbody, junctions, 'in_memory']:
        DM.Delete(item)

def main():
    nhd_subregion_gdb = arcpy.GetParameterAsText(0)
    output_table = arcpy.GetParameterAsText(1)
    lake_from_to(nhd_subregion_gdb, output_table)

if __name__ == '__main__':
    main()
