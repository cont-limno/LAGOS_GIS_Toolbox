# line density merge together
import os
import arcpy
from LineDensity import line_density

def multi_line_density(non_overlapping_subsets_dir, zonefield, lines, topoutfolder):
    arcpy.env.workspace = non_overlapping_subsets_dir
    fcs = arcpy.ListFeatureClasses("*NoOverlap*")
    temp_results = []
    for fc in fcs:
        result = line_density(fc, zonefield, lines, topoutfolder)
        temp_results.append(result)
    target_table = temp_results.pop(0)
    arcpy.Append_management(temp_results, target_table, 'NO_TEST')
    arcpy.CopyRows_management(target_table, out_table)

def main():
    non_overlapping_subsets_dir = arcpy.GetParameterAsText(0)
    zonefield = arcpy.GetParameterAsText(1)
    lines = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    multi_line_density(non_overlapping_subsets_dir, zonefield, lines, 'in_memory')
