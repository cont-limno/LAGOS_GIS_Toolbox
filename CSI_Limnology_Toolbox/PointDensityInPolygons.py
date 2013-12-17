# Filename: PointDensityInPolygon.py
# Purpose: Gives the density of points in polygons by point/hectare and point/sqkm.

import arcpy, os
arcpy.env.overwriteOutput = True
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()
arcpy.env.outputCoordinateSystem = albers


inpt = arcpy.GetParameterAsText(0)
inpoly = arcpy.GetParameterAsText(1)
addfield = arcpy.GetParameterAsText(2)
outfc = arcpy.GetParameterAsText(3)



mem = "in_memory"
arcpy.env.workspace = mem
arcpy.env.scratchWorkspace = mem

arcpy.FeatureClassToFeatureClass_conversion(inpoly, mem, "poly")
poly = "poly"
arcpy.FeatureClassToFeatureClass_conversion(inpt, mem, "pt")
pt = "pt"

arcpy.AddField_management(poly, "Ha", "DOUBLE")
arcpy.AddField_management(poly, "SqKm", "DOUBLE")
arcpy.AddField_management(poly, "PtPerHa", "DOUBLE")
arcpy.AddField_management(poly, "PtPerSqKm", "DOUBLE")
arcpy.AddField_management(poly, "PtCnt", "LONG")
expha = '!shape.area@hectares!'
expsqkm = '!shape.area@squarekilometers!'
arcpy.CalculateField_management(poly, "Ha", expha, "PYTHON")
arcpy.CalculateField_management(poly, "SqKm", expsqkm, "PYTHON")

fms = arcpy.FieldMappings()
fmha = arcpy.FieldMap()
fmsqkm = arcpy.FieldMap()
fmperha = arcpy.FieldMap()
fmpersqkm = arcpy.FieldMap()
fmcnt = arcpy.FieldMap()
fmadd = arcpy.FieldMap()
fmha.addInputField(poly, "Ha")
fmsqkm.addInputField(poly, "SqKm")
fmperha.addInputField(poly, "PtPerHa")
fmpersqkm.addInputField(poly, "PtPerSqKm")
fmcnt.addInputField(poly, "PtCnt")
fmadd.addInputField(poly, addfield)
fms.addFieldMap(fmadd)
fms.addFieldMap(fmha)
fms.addFieldMap(fmcnt)
fms.addFieldMap(fmsqkm)
fms.addFieldMap(fmperha)
fms.addFieldMap(fmpersqkm)



arcpy.SpatialJoin_analysis(poly, pt, outfc, '', '', fms)


expdenha = '!Join_Count! / !Ha!'
expdensqkm = '!Join_Count! / !SqKm!'
expcnt = '!Join_Count!'
arcpy.CalculateField_management(outfc, "PtPerHa", expdenha, "PYTHON")
arcpy.CalculateField_management(outfc, "PtPerSqKm", expdensqkm, "PYTHON")
arcpy.CalculateField_management(outfc, "PtCnt", expcnt, "PYTHON")
arcpy.DeleteField_management(outfc, ["Join_Count", "TARGET_FID", "Ha", "SqKm"])

 
