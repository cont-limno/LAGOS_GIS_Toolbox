# Filename: PercentHectaresInPoly.py
# Purpose: Calculate percent and hectares of zones that overlay another polygon feature class' extent.

import arcpy, os

zones = arcpy.GetParameterAsText(0)
idfield = arcpy.GetParameterAsText(1)
maskpoly = arcpy.GetParameterAsText(2)
suffix = arcpy.GetParameterAsText(3)
try:
    arcpy.AddField_management(zones, "Pct_In_" + suffix, "DOUBLE")
except:
    arcpy.AddMessage("Add field failed. Check your suffix for spaces or other invalid charcters.")

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
    arcpy.AddField_management(clip,"Ha_In_" + suffix, "DOUBLE")
except:
    pass
try:
    arcpy.AddField_management(zones,"Ha", "DOUBLE")
except:
    pass
exp = '!shape.area@hectares!'
arcpy.CalculateField_management(clip, "Ha_In_" + suffix, exp, "PYTHON")
arcpy.CalculateField_management(zones, "Ha", exp, "PYTHON")
arcpy.JoinField_management(zones, idfield, clip, idfield, "Ha_In_" + suffix)
arcpy.AddMessage("Calculating percentages...")
arcpy.RefreshCatalog(zones)
arcpy.RefreshCatalog(mem)
hain = "Ha_In_" + suffix
pct = '!%s! / !Ha! * 100' % (hain)
arcpy.CalculateField_management(zones, "Pct_In_" + suffix, pct, "PYTHON")
arcpy.AddMessage("Finished.")


