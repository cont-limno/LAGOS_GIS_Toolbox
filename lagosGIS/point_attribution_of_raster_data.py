# filename: point_attribution_of_raster_data.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): GEO
# tool type: re-usable (ArcGIS Toolbox)

import arcpy
import lagosGIS


def attribution(zone_points, zone_field, in_value_raster, out_table, rename_tag='', units=''):
    """
    Extracts the raster value at a point representing a zone when the zone is much smaller than the raster cell size.
    :param zone_points: Point feature class representing the zones or lakes
    :param zone_field: Unique identifier for each zone
    :param in_value_raster: The raster dataset to be summarized
    :param out_table: Output table to save the result
    :param rename_tag: (Optional) Text string containing prefix to append to all output columns
    :param units: (Optional) Text string containing units to append as a suffix to all output columns
    :return:
    """

    arcpy.env.workspace = 'in_memory'
    arcpy.CheckOutExtension("Spatial")

    # Extract values to points
    points = lagosGIS.select_fields(zone_points, 'points', [zone_field])
    point_stats = arcpy.sa.ExtractValuesToPoints(points, in_value_raster, 'point_stats', 'INTERPOLATE')

    # Convert NoData numeric codes to missing values in output table
    nodata = arcpy.Describe(in_value_raster).noDataValue
    if nodata:
        with arcpy.da.UpdateCursor(point_stats, 'RASTERVALU') as cursor:
            for row in cursor:
                if row[0] == nodata:
                    row[0] = None
                cursor.updateRow(row)

    # Rename fields, if elected
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
    attribution(zone_points, zone_field, in_value_raster, out_table, rename_tag, units)


if __name__ == '__main__':
    main()