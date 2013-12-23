# Filename: PrefixSuffix.py
# Purpose: Add a suffix to a dataset name.

import arcpy, os

inws = arcpy.GetParameterAsText(0)
prefix = arcpy.GetParameterAsText(1)
suffix = arcpy.GetParameterAsText(2)
filelist = []
for root, dirs, files in arcpy.da.Walk(inws):
    for file in files:
        filelist.append(os.path.join(root, file))
for file in filelist:
    name = os.path.join(inws, prefix + os.path.splitext(os.path.basename(file))[0] + suffix)
    arcpy.Rename_management(file, name)