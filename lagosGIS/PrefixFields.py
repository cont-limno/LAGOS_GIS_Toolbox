# Name:PrefixFields.py
# Purpose: Adds prefix to all field names in a table
# Author: Scott Stopyak
# Created: 11/26/2013
# Copyright © Scott Stopyak 2013
# Licence: Distributed under the terms of GNU GPL
#_________________________________________________________________________________


import os, sys, arcpy

inTable = arcpy.GetParameterAsText(0)
prefix = arcpy.GetParameterAsText(1)
outfolder = arcpy.GetParameterAsText(2)
arcpy.env.overwriteOutput = True
try:
    arcpy.CreateFileGDB_management(outfolder,"PrefixFields")
    gdb = os.path.join(outfolder, "PrefixFields.gdb")
    arcpy.RefreshCatalog(outfolder)
    inTableName = os.path.splitext(os.path.basename(inTable))[0]
    arcpy.TableToGeodatabase_conversion(inTable, gdb)
    table = os.path.join(gdb, os.path.splitext(os.path.basename(inTable))[0])
    arcpy.RefreshCatalog(outfolder)
except:
    pass

fields = arcpy.ListFields(table)
for f in fields:
    try:
        name = prefix + f.name
        type = f.type
        arcpy.AddField_management(table, name, type)
        exp = "!%s!" % (f.name)
        arcpy.CalculateField_management(table, name, exp, "PYTHON")
        arcpy.RefreshCatalog(outfolder)
        arcpy.DeleteField_management(table, [f.name])
        arcpy.RefreshCatalog(outfolder)
       
        del name
        del type
        del exp
    except:
        continue




