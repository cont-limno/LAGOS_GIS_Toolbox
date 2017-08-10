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
    nhd_waterbody = os.path.join(nhd_gdb, 'NHDWaterbody')
    hydro_net_junctions = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET_Junctions')
    hydro_net = os.path.join(nhd_gdb, 'Hydrography', 'HYDRO_NET')

    # get this hu4
    wbd_hu4 = os.path.join(nhd_gdb, "WBD_HU4")
    field_name = (arcpy.ListFields(wbd_hu4, "HU*4"))[0].name
    whereClause4 =  """{0} = '{1}'""".format(arcpy.AddFieldDelimiters(nhd_gdb, field_name), huc4_code)
    arcpy.Select_analysis(wbd_hu4, "hu4", whereClause4)

    # make layers for upcoming spatial selections
    # and fcs in memory
    arcpy.MakeFeatureLayer_management(hydro_net_junctions, "junctions")
    arcpy.MakeFeatureLayer_management(watersheds_fc, 'watersheds')

    all_lakes = os.path.join(pour_dir, 'pourpoints.gdb', 'eligible_lakes')
    arcpy.MakeFeatureLayer_management(all_lakes, "all_lakes_lyr")
##    arcpy.SelectLayerByLocation_management("all_lakes_lyr", "INTERSECT", "hu8")
    arcpy.CopyFeatures_management("all_lakes_lyr", 'eligible_lakes')

    # ten ha lakes and junctions
    if mode == 'interlake':
        tenha_where_clause = """"AreaSqKm" >= .1"""
        arcpy.Select_analysis("eligible_lakes", 'tenha_lakes', tenha_where_clause)
        arcpy.MakeFeatureLayer_management('tenha_lakes', 'tenha_lakes_lyr')
        arcpy.SelectLayerByLocation_management('junctions', 'INTERSECT', 'tenha_lakes', search_distance = "1 Meters")
        arcpy.CopyFeatures_management('junctions', 'tenha_junctions')
        arcpy.MakeFeatureLayer_management('tenha_junctions', 'tenha_junctions_lyr')
    # for each lake, calculate its interlake watershed in the upcoming block
    prog_count = int(arcpy.GetCount_management('eligible_lakes').getOutput(0))
    counter = 0

    with arcpy.da.SearchCursor('eligible_lakes', ["Permanent_Identifier"]) as cursor:
        for row in cursor:
            counter += 1
            if counter % 50 == 0:
                print("{0} out of {1} lakes completed.".format(counter, prog_count))
            id = row[0]
            where_clause = """"{0}" = '{1}'""".format("Permanent_Identifier", id)
            arcpy.MakeFeatureLayer_management('eligible_lakes', "this_lake",
                                                where_clause)
            arcpy.SelectLayerByLocation_management("junctions", "INTERSECT",
                                            "this_lake", search_distance = "1 Meters")
            count_jxns = int(arcpy.GetCount_management('junctions').getOutput(0))
            if count_jxns == 0:
                arcpy.SelectLayerByLocation_management('watersheds', 'CONTAINS', 'this_lake')
            else:
                arcpy.CopyFeatures_management("junctions", 'this_lake_jxns')
                if mode == 'interlake':
                    arcpy.SelectLayerByLocation_management('tenha_junctions_lyr', 'ARE_IDENTICAL_TO', 'this_lake_jxns')
                    arcpy.SelectLayerByAttribute_management('tenha_junctions_lyr', 'SWITCH_SELECTION')
                    arcpy.CopyFeatures_management('tenha_junctions_lyr', 'other_tenha_junctions')
                    arcpy.SelectLayerByLocation_management('tenha_lakes_lyr', 'INTERSECT', 'other_tenha_junctions', search_distance = '1 Meters')
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

            # Sometimes when the trace stops at 10-ha lake, that shed(s)
            # gets selected. Remove them with the tenha_lakes_lyr
            # that already has only OTHER lakes selected
            # using other_tenha_junctions causes some stuff to be picked up
            # that shouldn't be when junctions are right on boundaries
            if mode == 'interlake':
                arcpy.SelectLayerByLocation_management("watersheds", "CONTAINS", "tenha_lakes_lyr", selection_type = "REMOVE_FROM_SELECTION")
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

    arcpy.EliminatePolygonPart_management("output_fc", "output_hole_remove", "AREA", "3.9 Hectares", "0", "CONTAINED_ONLY")
    arcpy.Clip_analysis("output_hole_remove", "hu4", output_fc)
    arcpy.Delete_management('output_fc')
    arcpy.ResetEnvironments()

def test():
    watersheds_fc = 'C:/GISData/Scratch/watersheds_by_HU4_3dec2014.gdb/huc0411_merged_watersheds'
    nhd_gdb = r'E:\nhd\fgdb\NHDH0411.gdb'
    pour_dir =  r'C:\GISData\Scratch\new_pourpoints\pourpoints0411'
    output_fc = 'C:/GISData/Scratch/Scratch.gdb/INTERLAKE_DEC6'
    aggregate_watersheds(watersheds_fc, nhd_gdb, pour_dir,
                            output_fc, mode = 'interlake')
def main():
    watersheds_fc = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(1)
    pour_dir =  arcpy.GetParameterAsText(2)
    output_fc = arcpy.GetParameterAsText(3)
    aggregate_watersheds(watersheds_fc, nhd_gdb, pour_dir,
                            output_fc, mode = 'interlake')

if __name__ == '__main__':
    main()
