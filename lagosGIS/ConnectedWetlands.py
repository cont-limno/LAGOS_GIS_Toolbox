# ConnectedWetlands.py
# Characterizes each lake according to its wetland connections
# Output table has one row PER LAKE
# Tool steps summary
# 1)	Set environments
# 2)	Create a layer called 'lakes_30m' that is the lake polygons buffered by 30m. Use this throughout the script instead of the lakes themselves.
# 3)	Create a line-based lakes representation (from the buffered lakes) called 'shorelines'
# 4)	For each VegType selection (All, forested, scrub-shrub, open water, other):
#       a.	Apply the polygons_in_zones function from the CSI Limnology Toolbox using the lake as the zone, the wetlands as the polygon feature class of interest, and the current selection query
#       b.	Rename the output fields to be specific to this selection: 'Poly_Count' becomes 'ForestedWetlands_Count', for instance.
#       c.	Use the current selection query to make a 'selected_wetlands' layer
#       d.	Intersect the 'shorelines' layer with the 'selected_wetlands' layer
#       e.	Sum the length of all the shoreline-wetlands intersection for each lake: this is the shoreline connection length
#       f.	Use the csiutils.one_in_one_out and csiutils.redefine_nulls functions to ensure each input lake receives an output record even if it has no wetland connections and the values are 0
#       g.	Join the temporary output from step 4a to the shorelines output to make the final table
# 5)	Once all selections have been calculated, join all the tables together and ensure that even if, for instance, there were no 'other' wetlands that the fields are populated with 0s.
# 6)	Remove extra fields and clean up intermediates
import os
import arcpy
from arcpy import env
import csiutils as cu
from polygons_in_zones import polygons_in_zones

def connected_wetlands(lakes_fc, lake_id_field, wetlands_fc, out_table):
    env.workspace = 'in_memory'
    env.outputCoordinateSystem = arcpy.SpatialReference(102039)

    arcpy.Buffer_analysis(lakes_fc, 'lakes_30m', '30 meters')

    arcpy.FeatureToLine_management('lakes_30m', 'shorelines')

    # 3 selections for the wetlands types we want to look at
    openwater_exp = """"VegType" = 'PEMorPAB'"""
    forested_exp = """"VegType" = 'PFO'"""
    scrubshrub_exp = """"VegType" = 'PSS'"""
    other_exp = """"VegType" = 'Other'"""
    all_exp = ''


    selections = [all_exp, forested_exp, scrubshrub_exp, openwater_exp, other_exp]
    temp_tables = ['AllWetlands', 'ForestedWetlands', 'ScrubShrubWetlands', 'OpenWaterWetlands', 'OtherWetlands']

    # for each wetland type, get the count of intersection wetlands, and the length of the lake
    # shoreline that is within a wetland polygon
    for sel, temp_table in zip(selections, temp_tables):
        print("Creating temporary table for wetlands where {0}".format(sel))
        # this function adds the count and the area using the lake as the zone
        polygons_in_zones('lakes_30m', lake_id_field, wetlands_fc, temp_table, sel, contrib_area = True)

        # make good field names now rather than later
        for f in new_fields:
            cu.rename_field(temp_table, f, f.replace('Poly', temp_table), True)

        # shoreline calculation
        # using the Shape_Length field so can't do this part in memory
        shoreline_gdb = cu.create_temp_GDB('shoreline')
        selected_wetlands = os.path.join(shoreline_gdb, 'wetlands')
        arcpy.Select_analysis(wetlands_fc, selected_wetlands, sel)
        intersect_output = os.path.join(shoreline_gdb, "intersect")
        arcpy.Intersect_analysis(['shorelines', selected_wetlands], intersect_output)
        arcpy.Statistics_analysis(intersect_output, 'intersect_stats', [['Shape_Length', 'SUM']], lake_id_field)
        cu.one_in_one_out('intersect_stats', ['SUM_Shape_Length'], lakes_fc, lake_id_field, 'temp_shoreline_table')
        cu.redefine_nulls('temp_shoreline_table', ['SUM_Shape_Length'], [0])
        shoreline_field = temp_table + "_Shoreline_Km"
        arcpy.AddField_management('temp_shoreline_table', shoreline_field, 'DOUBLE')
        arcpy.CalculateField_management('temp_shoreline_table', shoreline_field, '!SUM_Shape_Length!/1000', 'PYTHON')

        # join the shoreline value to the temp_table
        arcpy.JoinField_management(temp_table, lake_id_field, 'temp_shoreline_table', lake_id_field, shoreline_field)

        # clean up shoreline intermediates
        for item in [shoreline_gdb, 'intersect_stats', 'temp_shoreline_table']:
            arcpy.Delete_management(item)

    # join em up and copy to final
    temp_tables.remove('AllWetlands')
    for t in temp_tables:
        try:
            arcpy.JoinField_management('AllWetlands', lake_id_field, t, lake_id_field)
        # sometimes there's no table if it was an empty selection
        except:
            empty_fields = [f.replace('Poly', t) for f in new_fields]
            for ef in empty_fields:
                arcpy.AddField_management('AllWetlands', ef, 'Double')
                arcpy.CalculateField_management('AllWetlands', ef, '0', 'PYTHON')
            continue
    # remove all the extra zone fields, which have underscore in name
    drop_fields = [f.name for f in arcpy.ListFields('AllWetlands', 'Permanent_Identifier_*')]
    for f in drop_fields:
        arcpy.DeleteField_management('AllWetlands', f)

    # remove all the overlapping metrics, which do not apply by definition
    fields = [f.name for f in arcpy.ListFields('AlLWetlands')]
    for f in fields:
        if 'Overlapping' in f:
            arcpy.DeleteField_management('AllWetlands', f)
    arcpy.CopyRows_management('AllWetlands', out_table)

    for item in ['AllWetlands'] + temp_tables:
        try:
            arcpy.Delete_management(item)
        except:
            continue

def main():
    lakes_fc = arcpy.GetParameterAsText(0)
    lake_id_field = arcpy.GetParameterAsText(1)
    wetlands_fc = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    connected_wetlands(lakes_fc, lake_id_field, wetlands_fc, out_table)

def test():
    lakes_fc = r'C:\GISData\Master_Geodata\MasterGeodatabase2014_ver4.gdb\Lacustrine\LAGOS_All_Lakes_4ha'
    lake_id_field = 'Permanent_Identifier'
    wetlands_fc = r'C:\GISData\Master_Geodata\MasterGeodatabase2014_ver4.gdb\Palustrine\Wetlands'
    out_table = r'C:\GISData\Attribution_Sept2014.gdb/LakeWetlandConnections_FIXED'
    connected_wetlands(lakes_fc, lake_id_field, wetlands_fc, out_table)

##    lakes_fc = r'C:\GISData\Scratch\Scratch.gdb\Lakes_OCT1'
##    lake_id_field = 'Permanent_Identifier'
##    wetlands_fc = r'C:\GISData\Scratch\Scratch.gdb\Wetlands_OCT1'
##    out_table = r'C:\GISData\Scratch\Scratch.gdb\ConnectedWetlands_OCT1TEST'
##    connected_wetlands(lakes_fc, lake_id_field, wetlands_fc, out_table)

if __name__ == '__main__':
    main()
