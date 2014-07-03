import os
import arcpy
from arcpy import env
import csiutils as cu

def refine_zonal_output(t, is_thematic):
    """Makes a nicer output for this tool. Rename some fields, drop unwanted
        ones, calculate percentages using raster AREA before deleting that
        field."""

    drop_fields = ['COUNT', 'AREA', 'RANGE', 'SUM', 'ZONE_CODE']
    if is_thematic:
        fields = arcpy.ListFields(t, "VALUE*")
        for f  in fields:
            # convert area to hectares in a new field
            ha_field = f.name.replace("VALUE", "Ha")
            arcpy.AddField_management(t, ha_field, f.type)
            expr = "!%s!/10000" % f.name
            arcpy.CalculateField_management(t, ha_field, expr, "PYTHON")

            # find percent of total area in a new field
            pct_field = f.name.replace("VALUE", "Pct")
            arcpy.AddField_management(t, pct_field, f.type)
            expr = "100 * !%s!/!AREA!" % f.name
            arcpy.CalculateField_management(t, pct_field, expr, "PYTHON")

            #Delete the old field
            arcpy.DeleteField_management(t, f.name)

    else:
        # continuous variables don't have these in the output
        drop_fields = drop_fields + ['VARIETY', 'MAJORITY', 'MINORITY', 'MEDIAN']

    for df in drop_fields:
        try:
            arcpy.DeleteField_management(t, df)
        except:
            continue

def stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic):
    arcpy.CheckOutExtension("Spatial")
    cu.multi_msg("Calculating zonal statistics...")
    temp_zonal_table = 'in_memory/zonal_stats_temp'
    temp_entire_table = 'in_memory/temp_entire_table'

    # calculate/doit
    env.snapRaster = in_value_raster
    env.cellSize = in_value_raster

    # this has to be on disk for some reason to avoid background processing
    # errors thrown up at random
    # hence we get the following awkward horribleness
    try:
        arcpy.sa.ZonalStatisticsAsTable(zone_fc, zone_field, in_value_raster,
                                temp_zonal_table, 'DATA', 'ALL')
    # with Permanent_Identifier as the zone_field, background processing errors
    # and another error get thrown up at random
    # it's faster to do zonal stats as above but if it fails (which it does
    # pretty quickly, usually), do this way which always works but takes
    # twice as long on large rasters
    except:
        temp_workspace = cu.create_temp_GDB('temp_zonal')
        convert_raster = os.path.join(temp_workspace,
                        cu.shortname(zone_fc) + '_converted')
        cu.multi_msg('Creating raster {0}'.format(convert_raster))
        arcpy.PolygonToRaster_conversion(zone_fc, zone_field, convert_raster)
        arcpy.sa.ZonalStatisticsAsTable(convert_raster, zone_field, in_value_raster,
                                    temp_zonal_table, "DATA", "ALL")

    if is_thematic:
        #for some reason env.celLSize doesn't work
        desc = arcpy.Describe(in_value_raster)
        cell_size = desc.meanCelLHeight

        # calculate/doit
        temp_area_table = 'in_memory/tab_area_temp'
        cu.multi_msg("Tabulating areas...")

        arcpy.sa.TabulateArea(convert_raster, zone_field, in_value_raster,
                                'Value', temp_area_table, cell_size)

        # making the output table
        arcpy.CopyRows_management(temp_area_table, temp_entire_table)
        zonal_stats_fields = ['VARIETY', 'MAJORITY', 'MINORITY', 'AREA', 'MEDIAN']
        arcpy.JoinField_management(temp_entire_table, zone_field, temp_zonal_table, zone_field, zonal_stats_fields)

        # cleanup
        arcpy.Delete_management(temp_area_table)

    if not is_thematic:
        # making the output table
        arcpy.CopyRows_management(temp_zonal_table, temp_entire_table)

    cu.multi_msg("Refining output table...")
    refine_zonal_output(temp_entire_table, is_thematic)



    #final table gets a record even for no-data zones
    keep_fields = [f.name for f in arcpy.ListFields(temp_entire_table)]
    if zone_field.upper() in keep_fields:
        keep_fields.remove(zone_field.upper())
    if zone_field in keep_fields:
        keep_fields.remove(zone_field)
    cu.one_in_one_out(temp_entire_table, keep_fields, zone_fc, zone_field, out_table)
##    cu.redefine_nulls(out_table, keep_fields, ["NA"]* len(keep_fields))

    # count whether all zones got an output record or not)
    out_count = int(arcpy.GetCount_management(temp_entire_table).getOutput(0))
    in_count = int(arcpy.GetCount_management(zone_fc).getOutput(0))
    if out_count < in_count:
        warn_msg = ("WARNING: {0} features are missing in the output table"
                    " because they are too small for this raster's"
                    " resolution. This may be okay depending on your"
                    " application.").format(in_count - out_count)
        arcpy.AddWarning(warn_msg)
        print(warn_msg)

    # cleanup
    arcpy.Delete_management(temp_zonal_table)
    arcpy.Delete_management(temp_entire_table)
    if arcpy.Exists(temp_workspace):
        arcpy.Delete_management(os.path.dirname(temp_workspace))
    arcpy.CheckInExtension("Spatial")

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    in_value_raster = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(4)
    is_thematic = arcpy.GetParameter(3) #boolean
    stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)


def test():
    zone_fc = 'C:/GISData/Master_Geodata/MasterGeodatabase2014_ver3.gdb/HU12'
    zone_field = 'ZoneID'
    in_value_raster = r'E:\Attribution_Rasters_2013\NewNADP\NO3\dep_no3_2012.tif'
    out_table = 'C:/GISData/Scratch/Scratch.gdb/test_zonal_warning'
    is_thematic = True
    stats_area_table(zone_fc, zone_field, in_value_raster, out_table, is_thematic)

if __name__ == '__main__':
    main()
