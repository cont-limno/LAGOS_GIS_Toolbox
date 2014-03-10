# line density merge together
import os
import arcpy
from LineDensity import line_density

def multi_line_density(non_overlapping_subsets_dir, zonefield, lines, out_table):
    arcpy.env.workspace = non_overlapping_subsets_dir
    fcs = arcpy.ListFeatureClasses("*NoOverlap*")
    full_fcs = [os.path.join(non_overlapping_subsets_dir, fc) for fc in fcs]
    arcpy.env.workspace = "in_memory"
    temp_tables = ["linedensity_" + os.path.splitext(fc)[0] for fc in fcs]
    for fc, t in zip(full_fcs, temp_tables):
        arcpy.AddMessage("Line density for subset %s" % fc)
        line_density(fc, zonefield, lines, t)

    target_table = temp_tables.pop(0)
    arcpy.Append_management(temp_tables, target_table, 'NO_TEST')
    arcpy.CopyRows_management(target_table, out_table)

def main():
    non_overlapping_subsets_dir = arcpy.GetParameterAsText(0)
    zonefield = arcpy.GetParameterAsText(1)
    lines = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    multi_line_density(non_overlapping_subsets_dir, zonefield, lines, out_table)

def test():
    non_overlapping_subsets_dir = 'C:/GISData/Scratch/Test_ZonalOverlap_Partial'
    zonefield = 'NHD_ID'
    lines = 'C:/GISData/Scratch/Scratch.gdb/test_IWS_streams_TINY'
    out_table = 'C:/GISData/Scratch/Scratch.gdb/test_multilinedensity_TINY'
    multi_line_density(non_overlapping_subsets_dir, zonefield, lines, out_table)


if __name__ == '__main__':
    main()
