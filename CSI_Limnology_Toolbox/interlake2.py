import os, re, shutil
import arcpy
import csiutils as cu

def aggregate_watersheds(watersheds_fc, lake_id_field, nhd_gdb, pour_dir,
                            output_fc, mode = ['interlake', 'cumulative']):
    """Creates a feature class with all the aggregated upstream watersheds for all
    eligible lakes (>4ha and certain FCodes) in this subregion."""

    # names
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()
    nhd_waterbody = os.path.join(nhd_gdb, 'NHDWaterbody')
    hydro_net_junctions = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET')

    # make layers for upcoming spatial selections
    # and fcs in memory
    arcpy.MakeFeatureLayer_management(hydro_net_junctions, "junctions")
    arcpy.MakeFeatureLayer_management(watersheds_fc, 'watersheds')

    arcpy.env.workspace = 'in_memory'
    all_lakes = os.path.join(pour_dir, 'pourpoints.gdb', 'eligible_lakes')
    arcpy.CopyFeatures_management(all_lakes, 'eligible_lakes')

    # ten ha lakes and junctions
    if mode == 'interlake':
        tenha_where_clause = """"AreaSqKm" >= .1"""
        arcpy.Select_analysis(all_lakes, 'tenha_lakes', tenha_where_clause)
        arcpy.SelectLayerByLocation_management('junctions', 'INTERSECT', 'tenha_lakes', search_distance = "1 Meters")
        arcpy.CopyFeatures_management('junctions', 'tenha_junctions')
        arcpy.MakeFeatureLayer_management('tenha_junctions', 'tenha_junctions_lyr')
    # for each lake, calculate its interlake watershed in the upcoming block

    with arcpy.da.SearchCursor('eligible_lakes', [lake_id_field]) as cursor:
        for row in cursor:
            id = row[0]
            cu.multi_msg("Aggregating watershed for lake ID {0}".format(id))
            where_clause = """"{0}" = '{1}'""".format(lake_id_field, id)
            arcpy.MakeFeatureLayer_management('eligible_lakes', "this_lake",
                                                where_clause)
            arcpy.SelectLayerByLocation_management("junctions", "INTERSECT",
                                            "this_lake", search_distance = "1 Meters")
            count_jxns = int(arcpy.GetCount_management('junctions').getOutput(0))
            if count_jxns == 0:
                arcpy.Select_analysis('watersheds', 'this_watershed', where_clause)
            else:
                arcpy.CopyFeatures_management("junctions", 'this_lake_jxns')
                if mode == 'interlake':
                    arcpy.TraceGeometricNetwork_management(hydro_net, "upstream",
                                    'this_lake_jxns', "TRACE_UPSTREAM", in_barriers = 'tenha_junctions_lyr')
                elif mode == 'cumulative':
                    arcpy.TraceGeometricNetwork_management(hydro_net, "upstream",
                                    'this_lake_jxns', "TRACE_UPSTREAM")

                arcpy.SelectLayerByLocation_management("watersheds", "INTERSECT",
                                    "upstream/NHDFlowline")
                arcpy.Dissolve_management("watersheds", "this_watershed")

            arcpy.Erase_analysis('this_watershed', 'this_lake',
                                'lakeless_watershed')
            if not arcpy.Exists(output_fc):
                arcpy.CopyFeatures_management('lakeless_watershed', output_fc)
                # to avoid append mismatch due to permanent_identifier
                cu.lengthen_field(output_fc, 'Permanent_Identifier', 255)
            else:
                arcpy.Append_management('lakeless_watershed', output_fc, 'NO_TEST')

            for item in ['this_lake', 'this_watershed', 'this_lake_jxns', 'upstream', 'lakeless_watershed']:
                try:
                    arcpy.Delete_management(item)
                except:
                    continue

    # Do we even need a line like the following?
##    arcpy.EliminatePolygonPart_management("merge", outname, "AREA", "3.9 Hectares", "0", "CONTAINED_ONLY")
    arcpy.ResetEnvironments()

def test():
    watersheds_fc = 'C:/GISData/Scratch/Scratch.gdb/huc04110001_final_watersheds'
    lake_id_field = 'Permanent_Identifier'
    nhd_gdb = r'E:\nhd\fgdb\NHDH0411.gdb'
    pour_dir =  r'C:\GISData\Scratch\NHD0411\NHD0411\pourpoints0411'
    output_fc = 'C:/GISData/Scratch/Scratch.gdb/INTERLAKE_OCT15'
    aggregate_watersheds(watersheds_fc, lake_id_field, nhd_gdb, pour_dir,
                            output_fc, mode = 'interlake')
def main():
    watersheds_fc = arcpy.GetParameterAsText(0)
    lake_id_field = arcpy.GetParameterAsText(1)
    nhd_gdb = arcpy.GetParameterAsText(2)
    pour_dir =  arcpy.GetParameterAsText(3)
    output_fc = arcpy.GetParameterAsText(4)
    aggregate_watersheds(watersheds_fc, lake_id_field, nhd_gdb, pour_dir,
                            output_fc, mode = 'interlake')

if __name__ == '__main__':
    main()
