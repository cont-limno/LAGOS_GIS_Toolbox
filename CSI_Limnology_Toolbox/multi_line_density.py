# line density merge together
import os, tempfile
import arcpy
from LineDensity import line_density

def multi_line_density(non_overlapping_subsets_dir, zonefield, lines, temp_dir):
    arcpy.env.workspace = non_overlapping_subsets_dir
    fcs = arcpy.ListFeatureClasses("*NoOverlap*")
    fcs = [os.path.join(non_overlapping_subsets_dir, fc) for fc in fcs]
    print(fcs)
    temp_results = []
    for fc in fcs:
        arcpy.AddMessage("Line density for subset %s" % fc)
        result = line_density(fc, zonefield, lines, temp_dir)
        temp_results.append(result)
    target_table = temp_results.pop(0)
    arcpy.Append_management(temp_results, target_table, 'NO_TEST')
    arcpy.CopyRows_management(target_table, out_table)


def main():
    non_overlapping_subsets_dir = arcpy.GetParameterAsText(0)
    zonefield = arcpy.GetParameterAsText(1)
    lines = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    temp_dir = os.path.join(tempfile.gettempdir(), 'linedensity')
    counter = 0
    while os.path.exists(temp_dir):
        temp_dir = os.path.join(tempfile.gettempdir(), 'linedensity%d' % counter)
        counter += 1
    os.mkdir(temp_dir)
    arcpy.AddMessage("Temp directory located at %s" % temp_dir)
    multi_line_density(non_overlapping_subsets_dir, zonefield, lines, temp_dir)


if __name__ == '__main__':
    main()
