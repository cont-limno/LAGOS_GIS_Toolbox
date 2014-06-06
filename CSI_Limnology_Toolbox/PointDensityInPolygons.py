# Filename: PointDensityInPolygon.py
# Purpose: Gives the density of points in polygons by point/hectare and point/sqkm.
import os
import arcpy


##import arcpy, os
##arcpy.env.overwriteOutput = True
##albers = arcpy.SpatialReference()
##albers.factoryCode = 102039
##albers.create()
##arcpy.env.outputCoordinateSystem = albers
##
##
##inpt = arcpy.GetParameterAsText(0)
##inpoly = arcpy.GetParameterAsText(1)
##addfield = arcpy.GetParameterAsText(2)
##out_table = arcpy.GetParameterAsText(3)
##
##
##
##mem = "in_memory"
##arcpy.env.workspace = mem
##arcpy.env.scratchWorkspace = mem
##
##arcpy.FeatureClassToFeatureClass_conversion(inpoly, mem, "poly")
##poly = "poly"
##arcpy.FeatureClassToFeatureClass_conversion(inpt, mem, "pt")
##pt = "pt"
##
##arcpy.AddField_management(poly, "Ha", "DOUBLE")
##arcpy.AddField_management(poly, "SqKm", "DOUBLE")
##arcpy.AddField_management(poly, "PtPerHa", "DOUBLE")
##arcpy.AddField_management(poly, "PtPerSqKm", "DOUBLE")
##arcpy.AddField_management(poly, "PtCnt", "LONG")
##expha = '!shape.area@hectares!'
##expsqkm = '!shape.area@squarekilometers!'
##arcpy.CalculateField_management(poly, "Ha", expha, "PYTHON")
##arcpy.CalculateField_management(poly, "SqKm", expsqkm, "PYTHON")
##
##fms = arcpy.FieldMappings()
##fmha = arcpy.FieldMap()
##fmsqkm = arcpy.FieldMap()
##fmperha = arcpy.FieldMap()
##fmpersqkm = arcpy.FieldMap()
##fmcnt = arcpy.FieldMap()
##fmadd = arcpy.FieldMap()
##fmha.addInputField(poly, "Ha")
##fmsqkm.addInputField(poly, "SqKm")
##fmperha.addInputField(poly, "PtPerHa")
##fmpersqkm.addInputField(poly, "PtPerSqKm")
##fmcnt.addInputField(poly, "PtCnt")
##fmadd.addInputField(poly, addfield)
##fms.addFieldMap(fmadd)
##fms.addFieldMap(fmha)
##fms.addFieldMap(fmcnt)
##fms.addFieldMap(fmsqkm)
##fms.addFieldMap(fmperha)
##fms.addFieldMap(fmpersqkm)
##
##
##
##arcpy.SpatialJoin_analysis(poly, pt, 'temp_fc', '', '', fms)
##
##
##expdenha = '!Join_Count! / !Ha!'
##expdensqkm = '!Join_Count! / !SqKm!'
##expcnt = '!Join_Count!'
##arcpy.CalculateField_management('temp_fc', "PtPerHa", expdenha, "PYTHON")
##arcpy.CalculateField_management('temp_fc', "PtPerSqKm", expdensqkm, "PYTHON")
##arcpy.CalculateField_management('temp_fc', "PtCnt", expcnt, "PYTHON")
##
##arcpy.CopyRows_management(
##arcpy.DeleteField_management(outfc, ["Join_Count", "TARGET_FID", "Ha", "SqKm"])
##

def points_in_zones(zone_fc, zone_field, points_fc, output_table):
    arcpy.env.workspace = 'in_memory'
    arcpy.SpatialJoin_analysis(zone_fc, points_fc, 'temp_fc',
                            'JOIN_ONE_TO_ONE', 'KEEP_ALL',
                            match_option= 'INTERSECT')

    field_names = ['PointCount', 'PointsPerHa', 'PointsPerSqKm']
    field_types = ['LONG', 'DOUBLE', 'DOUBLE']
    calc_expressions = ['!Join_Count!', '!Join_Count!/!shape.area@hectares!',
                '!Join_Count!/!shape.area@squarekilometers!']

    for fname, ftype, expr in zip(field_names, field_types, calc_expressions):
        arcpy.AddField_management('temp_fc', fname, ftype)
        arcpy.CalculateField_management('temp_fc', fname, expr, 'PYTHON')

    arcpy.CopyRows_management('temp_fc', output_table)
    keep_fields = [zone_field] + field_names
    out_fields = [f.name for f in arcpy.ListFields(output_table)]
    for f in out_fields:
        if f not in keep_fields:
            try:
                arcpy.DeleteField_management(output_table, f)
            except:
                continue

def main():
    zone_fc = arcpy.GetParameterAsText(0)
    zone_field = arcpy.GetParameterAsText(1)
    points_fc = arcpy.GetParameterAsText(2)
    output_table = arcpy.GetParameterAsText(3)
    points_in_zones(zone_fc, zone_field, points_fc, output_table)

def test():
    mgdb = 'C:/GISData/Master_Geodata/MasterGeodatabase2014_ver3.gdb'
    zone_fc = os.path.join(mgdb, 'HU12')
    zone_field = 'ZoneID'
    points_fc = os.path.join(mgdb, 'Dams')
    output_table = 'C:/GISData/Scratch/Scratch.gdb/test_points_tool'
    points_in_zones(zone_fc, zone_field, points_fc, output_table)

if __name__ == '__main__':
    main()

