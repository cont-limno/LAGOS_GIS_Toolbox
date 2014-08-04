#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      smithn78
#
# Created:     04/08/2014
# Copyright:   (c) smithn78 2014
# Licence:     <your licence>
#-------------------------------------------------------------------------------

def main():
    pass

if __name__ == '__main__':
    main()
import os
import arcpy
from arcpy import env
import csiutils as cu
from polygons_in_zones import polygons_in_zones

def connected_wetlands(wetlands_fc, wetland_id_field, lakes_fc, out_table):
    env.workspace = 'in_memory'
    env.outputCoordinateSystem = arcpy.SpatialReference(102039)

    arcpy.FeatureToLine_management(wetlands_fc, 'shorelines')

##    # 3 selections for the wetlands types we want to look at
##    forested_exp = """ "WETLAND_TY" = 'Freshwater Forested/Shrub Wetland' """
##    emergent_exp = """ "WETLAND_TY" = 'Freshwater Emergent Wetland' """
##    other_exp = """ "WETLAND_TY" = 'Other' """
##
##    selections = [forested_exp, emergent_exp, other_exp]
##    temp_tables = ['Forested', 'Emergent', 'Other']

##    # for each wetland, get the count of intersection wetlands, the total area
##    # of the lake that is overlapping with wetlands, and the length of the lake
##    # shoreline that is within a wetland polygon
##    for sel, temp_table in zip(selections, temp_tables):
##    print("Creating temporary table for wetlands where {0}".format(sel))
    temp_table = 'Lake'
    # this function adds the count and the area using the wetland as the zone
    polygons_in_zones(wetlands_fc, wetland_id_field, lakes_fc, temp_table)

    # make good field names now rather than later
    new_fields = ['Poly_AREA_ha', 'Poly_AREA_pct', 'Poly_Count']
    for f in new_fields:
        cu.rename_field(temp_table, f, f.replace('Poly', temp_table), True)

##    # shoreline calculation
##    # using the Shape_Length field so can't do this part in memory
##    shoreline_gdb = cu.create_temp_GDB('shoreline')
##    selected_wetlands = os.path.join(shoreline_gdb, 'lakes')
##    arcpy.Select_analysis(wetlands_fc, selected_wetlands, sel)
##    intersect_output = os.path.join(shoreline_gdb, "intersect")
    arcpy.Intersect_analysis(['shorelines', lakes_fc], intersect_output)
    arcpy.Statistics_analysis(intersect_output, 'intersect_stats', [['Shape_Length', 'SUM']], wetland_id_field)
    cu.one_in_one_out('intersect_stats', ['SUM_Shape_Length'], wetlands_fc, wetland_id_field, 'temp_shoreline_table')
    cu.redefine_nulls('temp_shoreline_table', ['SUM_Shape_Length'], [0])
    shoreline_field = temp_table + "_Shoreline_Km"
    arcpy.AddField_management('temp_shoreline_table', shoreline_field, 'DOUBLE')
    arcpy.CalculateField_management('temp_shoreline_table', shoreline_field, '!SUM_Shape_Length!/1000', 'PYTHON')

    # join the shoreline value to the temp_table
    arcpy.JoinField_management(temp_table, wetland_id_field, 'temp_shoreline_table', lake_id_field, shoreline_field)

    # clean up shoreline intermediates
    for item in [shoreline_gdb, 'intersect_stats', 'temp_shoreline_table']:
        arcpy.Delete_management(item)

##    # join em up and copy to final
##    temp_tables.remove('Forested')
##    for t in temp_tables:
##        try:
##            arcpy.JoinField_management('Forested', lake_id_field, t, lake_id_field)
##        # sometimes there's no table if it was an empty selection
##        except:
##            empty_fields = [f.replace('Poly', t) for f in new_fields]
##            for ef in empty_fields:
##                arcpy.AddField_management('Forested', ef, 'Double')
##                arcpy.CalculateField_management('Forested', ef, '0', 'PYTHON')
##            continue
##    # remove all the extra zone fields, which have underscore in name
##    drop_fields = [f.name for f in arcpy.ListFields('Forested', 'Permanent_Identifier_*')]
##    for f in drop_fields:
##        arcpy.DeleteField_management('Forested', f)
    arcpy.CopyRows_management(temp_table, out_table)
    arcpy.Delete_management(temp_table)

##    for item in ['Forested'] + temp_tables:
##        try:
##            arcpy.Delete_management(item)
##        except:
##            continue

def main():
    wetlands_fc = arcpy.GetParameterAsText(0)
    wetland_id_field = arcpy.GetParameterAsText(1)
    lakes_fc = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    connected_wetlands(wetlands_fc, wetland_id_field, lakes_fc, out_table)

def test():
    wetlands_fc = r'C:\Users\smithn78\CSI_Processing\CSI\TestData_0411.gdb\Lakes_1ha'
    wetland_id_field = 'WET_ID'
    lakes_fc  = r'C:\Users\smithn78\CSI_Processing\CSI\TestData_0411.gdb\Wetlands'
    out_table = 'C:/GISData/Scratch/Scratch.gdb/AAAtest_connectedwetlands'
    connected_wetlands(wetlands_fc, wetland_id_field, lakes_fc, out_table)

if __name__ == '__main__':
    main()
