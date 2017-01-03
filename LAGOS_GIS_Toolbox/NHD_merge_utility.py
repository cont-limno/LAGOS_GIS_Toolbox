#-------------------------------------------------------------------------------
# Name:        NHD_merge_utility
# Purpose: Merges features from pre-staged NHD subregion downloads, deletes ID
# duplicates by saving only the one with the latest FDate, and deletes geographic
# duplicates (different IDs) by saving the one with the latest FDate).
#
# Requirements: 1) nhdDir = Directory containing all the NHD subregions you want to merge
#               2) fcName = Feature class name for features you want to merge
#               3) outputDir = Output directory
#
# Author:      nicolejeansmith
#
# Created:     2016-12-20

#-------------------------------------------------------------------------------

# Merge any of the NHD-based layers into a seamless layer and apply a selection if desired
# do not delete any duplicates
import os
import arcpy
import assumptions
import csiutils as cu

def nhd_merge(gdb_list, example_feature_class_name, out_fc, selection = ''):
    arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(102039) # USA_Contiguous_Albers_Equal_Area_Conic_USGS_version
    arcpy.env.workspace = 'in_memory'

    gdb_list = [os.path.join(gdb, os.path.basename(example_feature_class_name)) for gdb in gdb_list]
    gdb0 = gdb_list.pop(0)
    desc = arcpy.Describe(gdb0)
    cu.multi_msg('Merging all features together...')
    arcpy.CopyFeatures_management(gdb0, 'temp_merged')
    cu.lengthen_field('temp_merged', 'Permanent_Identifier', 255)
    cu.merge_many(gdb_list, 'in_memory/the_rest_merged')
    arcpy.Append_management('in_memory/the_rest_merged', 'temp_merged', 'NO_TEST')
    # use in_memory explicitly here because i haven't figured out how to pass arcgis environments to my functions :(
    fc_temp = 'in_memory/temp_merged'
    fcount1 = int(arcpy.GetCount_management(fc_temp).getOutput(0))
    cu.multi_msg('Before selection and cleaning, feature count is {0}'.format(fcount1))
    if selection:
        cu.multi_msg('Selecting features...')
        arcpy.Select_analysis('temp_merged', 'in_memory/merged_select', selection)
        fc_temp = 'in_memory/merged_select'

    fcount2 = int(arcpy.GetCount_management(fc_temp).getOutput(0))
    cu.multi_msg('After selection and before cleaning, feature count is {0}'.format(fcount2))

    arcpy.CopyFeatures_management(fc_temp, out_fc)

    # cu.multi_msg('Removing complete duplicates...')
    # fc_temp_fields = [f.name for f in arcpy.ListFields(fc_temp) if f.type <> 'OID']
    # arcpy.DeleteIdentical_management(fc_temp, fields = [f.name for f in arcpy.ListFields(fc_temp) if f.type <> 'OID'])
    #
    # fcount3 = int(arcpy.GetCount_management(fc_temp).getOutput(0))
    # cu.multi_msg('After removing complete duplicates only, feature count is {0}'.format(fcount3))
    #
    # cu.multi_msg('Removing remaining ID duplicates...')
    # assumptions.remove_nhd_duplicates(fc_temp, 'Permanent_Identifier', 'in_memory/no_id_dupes')
    #
    # fcount4 = int(arcpy.GetCount_management(fc_temp).getOutput(0))
    # cu.multi_msg('After removing all ID duplicates, feature count is {0}'.format(fcount4))
    #
    # if desc.shapeType == 'Polygon':
    #     cu.multi_msg('Removing geographic duplicates and substantially overlapping features...')
    #     assumptions.remove_geographic_doubles('in_memory/no_id_dupes', out_fc, 'Permanent_Identifier', percent_overlap_allowed = 10)
    # cu.multi_msg('nhd_merge complete.')
    #
    # fcount5 = int(arcpy.GetCount_management(fc_temp).getOutput(0))
    # cu.multi_msg('Final feature count is {0}'.format(fcount5))

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