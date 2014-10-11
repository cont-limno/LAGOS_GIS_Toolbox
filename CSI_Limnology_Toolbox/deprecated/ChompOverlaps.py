# ChompOverlaps.py
# Removes overlaps by letting the first polygon chomp its overlapping area out of the second.

import arcpy, os
arcpy.env.overwriteOutput = True
inpoly = arcpy.GetParameterAsText(0)
field = arcpy.GetParameterAsText(1)
outfolder = arcpy.GetParameterAsText(2)
try:
    arcpy.CreateFileGDB_management(outfolder, "ChompOverlaps")
except:
    pass
scratch = os.path.join(outfolder, "ChompOverlaps.gdb")
arcpy.CopyFeatures_management(inpoly, os.path.join(scratch, "inpoly"))
scratchpoly = os.path.join(scratch, "inpoly")
mem = "in_memory"
arcpy.env.workspace = mem
arcpy.Split_analysis(inpoly, inpoly, field, mem, '1')
fcs = []
for root, dirs, files in arcpy.da.Walk(mem):
    for file in files:
        fcs.append(os.path.join(root, file)

for fc in fcs:
    arcpy.Erase_analysis(scratchpoly, fc, os.path.join(scratch, "outpoly"))
        