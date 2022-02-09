# filename: NHD_merge_utility.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): LOCUS, GEO
# tool type: re-usable (ArcGIS Toolbox)

# Merge any of the NHD-based layers into a seamless layer and apply a selection if desired
# do not delete any duplicates
import os
import arcpy
import lagosGIS


def nhd_merge(gdb_list, example_feature_class_name, out_fc, selection = ''):
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039) # USA_Contiguous_Albers_Equal_Area_Conic_USGS_version
    arcpy.env.workspace = 'in_memory'

    gdb_list = [os.path.join(gdb, os.path.basename(example_feature_class_name)) for gdb in gdb_list]
    gdb0 = gdb_list.pop(0)
    desc = arcpy.Describe(gdb0)
    lagosGIS.multi_msg('Merging all features together...')
    arcpy.CopyFeatures_management(gdb0, 'temp_merged')
    lagosGIS.lengthen_field('temp_merged', 'Permanent_Identifier', 255)
    lagosGIS.merge_many(gdb_list, 'in_memory/the_rest_merged')
    arcpy.Append_management('in_memory/the_rest_merged', 'temp_merged', 'NO_TEST')
    # use in_memory explicitly here because i haven't figured out how to pass arcgis environments to my functions :(
    fc_temp = 'in_memory/temp_merged'
    fcount1 = int(arcpy.GetCount_management(fc_temp).getOutput(0))
    lagosGIS.multi_msg('Before selection and cleaning, feature count is {0}'.format(fcount1))
    if selection:
        lagosGIS.multi_msg('Selecting features...')
        arcpy.Select_analysis('temp_merged', 'in_memory/merged_select', selection)
        fc_temp = 'in_memory/merged_select'

    fcount2 = int(arcpy.GetCount_management(fc_temp).getOutput(0))
    lagosGIS.multi_msg('After selection and before cleaning, feature count is {0}'.format(fcount2))

    arcpy.CopyFeatures_management(fc_temp, out_fc)


def main():
    gdb_list = arcpy.GetParameterAsText(0).split(';') # list
    feature_class_name = arcpy.GetParameterAsText(1)
    selection = arcpy.GetParameterAsText(2)
    out_fc = arcpy.GetParameterAsText(3)
    nhd_merge(gdb_list, feature_class_name, out_fc, selection)

if __name__ == '__main__':
    main()