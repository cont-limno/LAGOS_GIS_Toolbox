import os
import arcpy
from arcpy import env
import csiutils as cu
import zonal_tabarea


def stats_overlap(non_overlapping_zones_list, zone_field, in_value_raster, out_table, is_thematic):
    temp_out_tables = ['C:/GISData/Scratch/fake_memory.gdb/' + os.path.basename(zfc) + "_temp_table" for zfc in non_overlapping_zones_list]

    arcpy.CheckOutExtension("Spatial")
    for zones, temp_table in zip(non_overlapping_zones_list, temp_out_tables):
        zonal_tabarea.stats_area_table(zones, zone_field, in_value_raster, temp_table, is_thematic)
    arcpy.CheckInExtension("Spatial")

    # doing this append/copy method instead of merge prevents problems with
    # differences in the field length of the zone field created by
    # Zonal Statistics As Table, merge doesn't have 'NO_TEST' option.
    target_table = temp_out_tables.pop(0)
    arcpy.Append_management(temp_out_tables, target_table, 'NO_TEST')
    arcpy.CopyRows_management(target_table, out_table)

    in_count = 0
    for zones in non_overlapping_zones_list:
        in_count += int(arcpy.GetCount_management(zones).getOutput(0))
    out_count = int(arcpy.GetCount_management(out_table).getOutput(0))
    if out_count < in_count:
        warn_msg = ("WARNING: {0} features are missing in the output table"
                    " because they are too small for this raster's"
                    " resolution. This may be okay depending on your"
                    " application.").format(in_count - out_count)
        arcpy.AddWarning(warn_msg)
        print(warn_msg)

def main():
    non_overlapping_zones_list = arcpy.GetParameterAsText(0) # list
    zone_field = arcpy.GetParameterAsText(1)
    in_value_raster = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    is_thematic = arcpy.GetParameter(4) #boolean

    stats_overlap(non_overlapping_zones_list, zone_field, in_value_raster, out_table, is_thematic)

def test():
    arcpy.env.workspace = 'C:/GISData/Scratch/Scratch.gdb'
    non_overlapping_zones_list = arcpy.ListFeatureClasses('test_IWS_teeny_NoOverlap*')
    zone_field = 'ZoneID'
    in_value_raster = r'E:\Attribution_Rasters_2013\NewNADP\NO3\dep_no3_2012.tif'
    out_table = 'C:/GISData/Scratch/Scratch.gdb/test_IWS_dep_no3_2012'
    is_thematic = False

    stats_overlap(non_overlapping_zones_list, zone_field, in_value_raster, out_table, is_thematic)

if __name__ == '__main__':
    main()
