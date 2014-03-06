import os
import arcpy
from arcpy import env

def refine_zonaltab_table(t, tab_area):
    if tab_area:
        fields = arcpy.ListFields(t, "VALUE*")
        for f in fields:
            # convert area to hectares in a new field
            ha_field = f.name.replace("VALUE", "Ha")
            arcpy.AddField_management(t, ha_field, f.type)
            expr = "!%s!/10000" % f.name
            arcpy.CalculateField_management(t, ha_field, expr, "PYTHON")

            # find percent of total area in a new field
            pct_field = f.name.replace("VALUE", "Pct")
            arcpy.AddField_management(t, pct_field, f.type)
            expr = "!%s!/!AREA!" % f.name
            arcpy.CalculateField_management(t, pct_field, expr, "PYTHON")


        #Delete the old field
        arcpy.DeleteField_management(t, f.name)

    drop_fields = ['COUNT', 'AREA', 'RANGE', 'SUM', 'ZONE_CODE']
    for df in drop_fields:
        try:
            arcpy.DeleteField_management(t, df)
        except:
            continue

##            #Add "AREA" field in hectares
##            arcpy.AddField_management(t, "AREA_ha", "Double")
##            expr = "!AREA!/10000"
##            arcpy.CalculateField_management(t, "AREA_ha", expr, "PYTHON")

##            #Delete old area field
##            arcpy.DeleteField_management(t, "AREA")

def stats_area_table(zone_fc, zone_field, in_value_raster, out_table, tab_area):
    arcpy.AddMessage("Calculating zonal statistics...")
    temp_zonal_table = 'in_memory/zonal_stats_temp'
    arcpy.sa.ZonalStatisticsAsTable(zone_fc, zone_field, in_value_raster, temp_zonal_table)

    if tab_area == True:
        temp_area_table = 'in_memory/tab_area_temp'
        desc = arcpy.Describe(in_value_raster)
        cell_size = desc.meanCellHeight
        arcpy.AddMessage("Tabulating areas...")
        arcpy.sa.TabulateArea(zone_fc, zone_field, in_value_raster, 'Value', temp_area_table, cell_size)

        arcpy.CopyRows_management(temp_area_table, out_table)

        zonal_stats_fields = ['VARIETY', 'MAJORITY', 'MINORITY', 'AREA', 'MEDIAN']
        arcpy.JoinField_management(out_table, zone_field, temp_zonal_table, zone_field, zonal_stats_fields)

    if tab_area == False:
        arcpy.CopyRows_management(temp_zonal_table, out_table)

    arcpy.AddMessage("Refining output table...")
    refine_zonaltab_table(out_table, tab_area)

    arcpy.AddMessage("Complete.")

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    in_value_raster = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    tab_area = arcpy.GetParameter(4) #boolean

    arcpy.CheckOutExtension("Spatial")
    stats_area_table(zone_fc, zone_field, in_value_raster, out_table, tab_area)
    arcpy.CheckInExtension("Spatial")

def test():
    zone_fc = 'C:/GISData/Scratch/Test_ZonalOverlap'
    zone_field = 'NHD_ID'
    in_value_raster = 'E:/Attribution_Rasters_2013/Cropland/crops_CDL_2006.tif'
    out_table = 'C:/GISData/Scratch/Scratch.gdb/test_newzonal_table'
    tab_area = True

    arcpy.CheckOutExtension("Spatial")
    stats_area_table(zone_fc, zone_field, in_value_raster, out_table, tab_area)
    arcpy.CheckInExtension("Spatial")

if __name__ == '__main__':
    main()
