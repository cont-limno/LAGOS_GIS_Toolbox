import arcpy
import lagosGIS


def point_attribution_of_raster_data(zone_points, zone_field, in_value_raster, out_table, rename_tag='', units=''):
    arcpy.env.workspace = 'in_memory'
    arcpy.CheckOutExtension("Spatial")

    points = lagosGIS.select_fields(zone_points, 'points', [zone_field])
    point_stats = arcpy.sa.ExtractValuesToPoints(points, in_value_raster, 'point_stats', 'INTERPOLATE')

    nodata = arcpy.Describe(in_value_raster).noDataValue
    if nodata:
        with arcpy.da.UpdateCursor(point_stats, 'RASTERVALU') as cursor:
            for row in cursor:
                if row[0] == nodata:
                    row[0] = None
                cursor.updateRow(row)

    if rename_tag:
        new_field_name = '{}_{}'.format(rename_tag, units)
        lagosGIS.rename_field(point_stats, 'RASTERVALU', new_field_name, deleteOld=True)
    arcpy.CopyRows_management(point_stats, out_table)
    return out_table

def main():
    zone_points = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    in_value_raster = arcpy.GetParameterAsText(2)
    out_table = arcpy.GetParameterAsText(3)
    rename_tag = arcpy.GetParameterAsText(4)
    units = arcpy.GetParameterAsText(5)
    point_attribution_of_raster_data(zone_points, zone_field, in_value_raster, out_table, rename_tag, units)

if __name__ == '__main__':
    main()