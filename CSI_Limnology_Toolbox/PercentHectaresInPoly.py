# Filename: PercentHectaresInPoly.py
# Purpose: Calculate percent and hectares of zones that overlay another polygon feature class' extent.

import arcpy, os

zones = arcpy.GetParameterAsText(0)
idfield = arcpy.GetParameterAsText(1)
maskpoly = arcpy.GetParameterAsText(2)
arcpy.AddField_management(zones, "Pct_In", "DOUBLE")

mem = "in_memory"
arcpy.env.workspace = mem
arcpy.AddMessage("Dissolving mask...")
arcpy.Dissolve_management(maskpoly, os.path.join(mem, "mask"))
mask = "mask"
arcpy.AddMessage("Clipping zones...")
arcpy.Clip_analysis(zones, mask, os.path.join(mem, "clip"))
clip = "clip"
arcpy.AddMessage("Adding Hectare fields...")
try:
    arcpy.AddField_management(clip,"Ha_In", "DOUBLE")
except:
    pass
try:
    arcpy.AddField_management(zones,"Ha", "DOUBLE")
except:
    pass
exp = '!shape.area@hectares!'
arcpy.CalculateField_management(clip, "Ha_In", exp, "PYTHON")
arcpy.CalculateField_management(zones, "Ha", exp, "PYTHON")
arcpy.JoinField_management(zones, idfield, clip, idfield, "Ha_In")
arcpy.AddMessage("Calculating percentages...")
arcpy.RefreshCatalog(zones)
arcpy.RefreshCatalog(mem)

pct = '!Ha_In! / !Ha! * 100'
arcpy.CalculateField_management(zones, "Pct_In", pct, "PYTHON")
arcpy.AddMessage("Finished.")


