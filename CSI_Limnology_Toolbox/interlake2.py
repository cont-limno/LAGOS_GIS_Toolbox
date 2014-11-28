import os, re, shutil
import arcpy
import csiutils as cu

def aggregate_watersheds(watersheds_fc, nhd_gdb, pour_dir,
                            output_fc, mode = ['interlake', 'cumulative']):
    """Creates a feature class with all the aggregated upstream watersheds for all
    eligible lakes (>4ha and certain FCodes) in this subregion."""
    arcpy.env.workspace = 'in_memory'

    # names
    huc4_code = re.search('\d{4}', os.path.basename(nhd_gdb)).group()
    huc8_code = re.search('\d{8}', os.path.basename(watersheds_fc)).group()
    nhd_waterbody = os.path.join(nhd_gdb, 'NHDWaterbody')
    hydro_net_junctions = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET')

    # get this hu8
    wbd_hu8 = os.path.join(nhd_gdb, "WBD_HU8")
    field_name = (arcpy.ListFields(wbd_hu8, "HU*8"))[0].name
    whereClause8 =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc8_code)
    arcpy.Select_analysis(wbd_hu8, "hu8", whereClause8)

    # make layers for upcoming spatial selections
    # and fcs in memory
    arcpy.MakeFeatureLayer_management(hydro_net_junctions, "junctions")
    arcpy.MakeFeatureLayer_management(watersheds_fc, 'watersheds')

    all_lakes = os.path.join(pour_dir, 'pourpoints.gdb', 'eligible_lakes')
    arcpy.MakeFeatureLayer_management(all_lakes, "all_lakes_lyr")
    arcpy.SelectLayerByLocation_management("all_lakes_lyr", "INTERSECT", "hu8")
    arcpy.CopyFeatures_management("all_lakes_lyr", 'eligible_lakes')

    # ten ha lakes and junctions
    if mode == 'interlake':
        tenha_where_clause = """"AreaSqKm" >= .1"""
        arcpy.Select_analysis("eligible_lakes", 'tenha_lakes', tenha_where_clause)
        arcpy.SelectLayerByLocation_management('junctions', 'INTERSECT', 'tenha_lakes', search_distance = "1 Meters")
        arcpy.CopyFeatures_management('junctions', 'tenha_junctions')
        arcpy.MakeFeatureLayer_management('tenha_junctions', 'tenha_junctions_lyr')
    # for each lake, calculate its interlake watershed in the upcoming block

    with arcpy.da.SearchCursor('eligible_lakes', ["Permanent_Identifier"]) as cursor:
        for row in cursor:
            id = row[0]
            where_clause = """"{0}" = '{1}'""".format("Permanent_Identifier", id)
            arcpy.MakeFeatureLayer_management('eligible_lakes', "this_lake",
                                                where_clause)
            arcpy.SelectLayerByLocation_management("junctions", "INTERSECT",
                                            "this_lake", search_distance = "1 Meters")
            count_jxns = int(arcpy.GetCount_management('junctions').getOutput(0))
            if count_jxns == 0:
                arcpy.SelectLayerByLocation_management('watersheds', 'CONTAINS', 'this_lake')
                arcpy.CopyFeatures_management('watersheds', 'this_watershed')
            else:
                arcpy.CopyFeatures_management("junctions", 'this_lake_jxns')
                if mode == 'interlake':
                    arcpy.SelectLayerByLocation_management('tenha_junctions_lyr', 'ARE_IDENTICAL_TO', 'this_lake_jxns')
                    arcpy.SelectLayerByAttribute_management('tenha_junctions_lyr', 'SWITCH_SELECTION')
                    arcpy.CopyFeatures_management('tenha_junctions_lyr', 'other_tenha_junctions')
                    arcpy.TraceGeometricNetwork_management(hydro_net, "upstream",
                                    'this_lake_jxns', "TRACE_UPSTREAM", in_barriers = 'other_tenha_junctions')
                elif mode == 'cumulative':
                    arcpy.TraceGeometricNetwork_management(hydro_net, "upstream",
                                    'this_lake_jxns', "TRACE_UPSTREAM")
                arcpy.SelectLayerByLocation_management("watersheds", "CONTAINS",
                                    "upstream/NHDFlowline")
                arcpy.SelectLayerByLocation_management("watersheds", 'CROSSED_BY_THE_OUTLINE_OF', 'upstream/NHDFLowline', selection_type = "ADD_TO_SELECTION")
                watersheds_count = int(arcpy.GetCount_management("watersheds").getOutput(0))
                if watersheds_count == 0:
                    arcpy.SelectLayerByLocation_management('watersheds', 'CONTAINS', 'this_lake')
                    arcpy.CopyFeatures_management('watersheds', 'this_watershed')
                else:

                    # Sometimes when the trace stops at 10-ha lake, that shed(s)
                    # gets selected. Remove it or them.
                    if mode == 'interlake':
                        arcpy.SelectLayerByLocation_management("watersheds", "CONTAINS", "other_tenha_junctions", selection_type = "REMOVE_FROM_SELECTION")
                    arcpy.Dissolve_management("watersheds", "this_watershed")
                    arcpy.AddField_management("this_watershed", 'Permanent_Identifier', 'TEXT', field_length = 255)
                    arcpy.CalculateField_management("this_watershed", "Permanent_Identifier", """'{}'""".format(id), "PYTHON")
                    dissolve_fields = arcpy.ListFields('this_watershed')
            arcpy.Erase_analysis('this_watershed', 'this_lake',
                                'lakeless_watershed')

            if not arcpy.Exists("output_fc"):
                arcpy.CopyFeatures_management('lakeless_watershed', "output_fc")
                # to avoid append mismatch due to permanent_identifier
                cu.lengthen_field("output_fc", 'Permanent_Identifier', 255)
            else:
                arcpy.Append_management('lakeless_watershed', "output_fc", 'NO_TEST')
            for item in ['this_lake', 'this_watershed', 'this_lake_jxns', 'upstream', 'lakeless_watershed']:
                try:
                    arcpy.Delete_management(item)
                except:
                    continue

    arcpy.CopyFeatures_management("output_fc", output_fc)

    # Do we even need a line like the following?
##    arcpy.EliminatePolygonPart_management("merge", outname, "AREA", "3.9 Hectares", "0", "CONTAINED_ONLY")
    arcpy.ResetEnvironments()

def test():
    watersheds_fc = 'C:/GISData/Scratch/new_watersheds_nov27.gdb/huc05030104_final_watersheds'
    nhd_gdb = r'E:\nhd\fgdb\NHDH0503.gdb'
    pour_dir =  r'C:\GISData\Scratch\new_pourpoints\pourpoints0503'
    output_fc = 'C:/GISData/Scratch/Scratch.gdb/INTERLAKE_NOV27_05030104'
    aggregate_watersheds(watersheds_fc, nhd_gdb, pour_dir,
                            output_fc, mode = 'interlake')
def main():
    watersheds_fc = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(2)
    pour_dir =  arcpy.GetParameterAsText(3)
    output_fc = arcpy.GetParameterAsText(4)
    aggregate_watersheds(watersheds_fc, nhd_gdb, pour_dir,
                            output_fc, mode = 'interlake')

if __name__ == '__main__':
    main()
