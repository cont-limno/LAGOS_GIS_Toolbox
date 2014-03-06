import os
import arcpy
from arcpy import env
from zonal_tabarea import refine_zonaltab_table

def stats_overlap(non_overlapping_zones_dir, zone_field, in_value_raster, out_table, tab_area):
    env.workspace = non_overlapping_zones_dir
    zone_fcs = arcpy.ListFeatureClasses('*NoOverlap*')
    temp_out_tables = ['in_memory/' + os.path.splitext(zfc)[0] + "_zonal_stats_table" for zfc in zone_fcs]
    arcpy.AddMessage("Calculating zonal statistics...")
    for zfc, t in zip(zone_fcs, temp_out_tables):
        arcpy.sa.ZonalStatisticsAsTable(zfc, zone_field, in_value_raster, t)
    target_zonal_table = temp_out_tables.pop(0)
    arcpy.Append_management(temp_out_tables, target_zonal_table, 'NO_TEST')

    if tab_area == True:
        temp_out_tables_area = [t + '_area' for t in temp_out_tables]
        desc = arcpy.Describe(in_value_raster)
        cell_size = desc.meanCellHeight
        arcpy.AddMessage("Tabulating areas...")
        for zfc, t_area in zip(zone_fcs, temp_out_tables_area):
            arcpy.sa.TabulateArea(zfc, zone_field, in_value_raster, 'Value', t_area, cell_size)

        target_table_area = temp_out_tables_area.pop(0)
        arcpy.Append_management(temp_out_tables_area, target_table_area, 'NO_TEST')
        arcpy.CopyRows_management(target_table_area, out_table)

        zonal_stats_fields = ['VARIETY', 'MAJORITY', 'MINORITY', 'AREA', 'MEDIAN']
        arcpy.JoinField_management(out_table, zone_field, target_zonal_table, zone_field, zonal_stats_fields)

    if tab_area == False:
        arcpy.CopyRows_management(target_zonal_table, out_table)

    arcpy.AddMessage("Refining output table...")
    refine_zonaltab_table(out_table, tab_area)

    arcpy.AddMessage("Complete.")

def main():
    non_overlapping_zones_dir = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    in_value_raster = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    tab_area = arcpy.GetParameter(4) #boolean

    arcpy.CheckOutExtension("Spatial")
    stats_overlap(non_overlapping_zones_dir, zone_field, in_value_raster, out_table, tab_area)

    arcpy.CheckInExtension("Spatial")

def test():
    non_overlapping_zones_dir = 'C:/GISData/Scratch/Test_ZonalOverlap'
    zone_field = 'NHD_ID'
    in_value_raster = 'E:/Attribution_Rasters_2013/Cropland/crops_CDL_2006.tif'
    out_table = 'C:/GISData/Scratch/Scratch.gdb/test_newzonal_table'
    tab_area = True

    arcpy.CheckOutExtension("Spatial")
    stats_overlap(non_overlapping_zones_dir, zone_field, in_value_raster, out_table, tab_area)
    arcpy.CheckInExtension("Spatial")

if __name__ == '__main__':
    main()
