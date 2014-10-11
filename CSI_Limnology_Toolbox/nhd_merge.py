# Merge any of the NHD-based layers into a seamless layer and apply a selection if desired
import os
import arcpy
import assumptions
import csiutils as cu

def nhd_merge(gdb_list, example_feature_class_name, out_fc, selection = ''):
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039)
    arcpy.env.workspace = 'in_memory'

    gdb_list = [os.path.join(gdb, os.path.basename(example_feature_class_name)) for gdb in gdb_list]
    gdb0 = gdb_list.pop(0)
    desc = arcpy.Describe(gdb0)
    cu.multi_msg('Merging all features together...')
    arcpy.CopyFeatures_management(gdb0, 'temp_merged')
    cu.lengthen_field('temp_merged', 'Permanent_Identifier', 255)
    arcpy.Append_management(gdb_list, 'temp_merged', 'NO_TEST')
    # use in_memory explicitly here because i haven't figured out how to pass arcgis environments to my functions :(
    if selection:
        cu.multi_msg('Selecting features...')
        arcpy.Select_analysis('temp_merged', 'in_memory/merged_select', selection)
    cu.multi_msg('Removing ID duplicates...')
    assumptions.remove_nhd_duplicates('in_memory/merged_select', 'Permanent_Identifier', 'in_memory/no_id_dupes')

    if desc.shapeType == 'Polygon':
        cu.multi_msg('Removing geographic duplicates and substantially overlapping features...')
        assumptions.remove_geographic_doubles('in_memory/no_id_dupes', out_fc, 'Permanent_Identifier', percent_overlap_allowed = 10)
    cu.multi_msg('nhd_merge complete.')

def test():
    mgd = 'C:/GISData/Master_Geodata/MasterGeodatabase2014_ver4.gdb'
    hu4 = os.path.join(mgd, 'HU4')
    subregions = []
    with arcpy.da.SearchCursor(hu4, 'HUC4') as cursor:
        for row in cursor:
            subregions.append(row[0])
    print subregions
    nhd_dir = 'E:/nhd/fgdb'
    gdb_list = [os.path.join(nhd_dir, 'NHDH{}.gdb'.format(s)) for s in subregions]
    feature_class_name = 'NHDArea'
    selection = """"FType" = 460"""
    out_fc = 'C:/GISData/Scratch/Scratch.gdb/nhd_merge_test_ALL'
    nhd_merge(gdb_list, feature_class_name, out_fc, selection)

def main():
    gdb_list = arcpy.GetParameterAsText(0).split(';') # list
    feature_class_name = arcpy.GetParameterAsText(1)
    selection = arcpy.GetParameterAsText(2)
    out_fc = arcpy.GetParameterAsText(3)
    nhd_merge(gdb_list, feature_class_name, out_fc, selection)

if __name__ == '__main__':
    main()