# Name:WetlandsInZones.py
# Purpose: Gives a count and area in hectares of wetlands intersecting zones.
# Author: Scott Stopyak
# Created: 19/11/2013
# Copyright:(c) Scott Stopyak 2013
# Licence: Distributed under the terms of GNU GPL
#_______________________________________________________________________________

import os
import arcpy
import lagosGIS


def wetlands_in_zones(infolder, idfield, wetlands, top_outfolder):


    # Create output geodatabase in outfolder
    out_gdb = os.path.join(top_outfolder, "WetlandsInZones.gdb")
    if not arcpy.Exists(out_gdb):
        arcpy.CreateFileGDB_management(top_outfolder, "WetlandsInZones")


    # Add WetlandHa field if it doesn't exist
    if len(arcpy.ListFields(wetlands, 'WetlandHa')) == 0:
        arcpy.AddField_management(wetlands, "WetlandHa", "DOUBLE")
    expha = "!shape.area@hectares!"
    arcpy.CalculateField_management(wetlands, "WetlandHa", expha, "PYTHON")

    # Set in memory as workspace. Intermediate output will be held in RAM.
    mem = "in_memory"
    arcpy.env.workspace = mem

    # Make wetlands in memory.
    exp = """"ATTRIBUTE" LIKE 'P%'AND "WETLAND_TY" <> 'Freshwater_Pond'"""
    arcpy.Select_analysis(wetlands, "wetlandspoly", exp)

    # Convert wetlands to points
    arcpy.FeatureToPoint_management("wetlandspoly", "wetlands", "INSIDE")

    # List extent feature classes
    fcs = []
    for root, dirs, files in arcpy.da.Walk(infolder):
        for file in files:
            fcs.append(os.path.join(root,file))

    # Spatial Join the wetlands to each extent
    out_fcs = []
    for fc in fcs:
        lagosGIS.multi_msg("Creating results for %s" % fc)
        name = os.path.basename(fc)
        fms = arcpy.FieldMappings()
        fmid = arcpy.FieldMap()
        fmha = arcpy.FieldMap()
        fmid.addInputField(fc, idfield)
        fmha.addInputField("wetlands", "WetlandHa")
        fmha.mergeRule = 'Sum'
        fms.addFieldMap(fmid)
        fms.addFieldMap(fmha)
        out_fc = os.path.join(out_gdb, name + "_Wetlands")
        arcpy.SpatialJoin_analysis(fc, wetlands, out_fc ,'','',fms)
        out_fcs.append(out_fc)


    # Export feature classes attribute tables to tables
    for f in out_fcs:
        arcpy.CopyRows_management(f, os.path.join(out_gdb, "Table" + os.path.basename(f)))

def main():
    infolder = arcpy.GetParameterAsText(0) # Workspace with zone feature classes
    idfield = arcpy.GetParameterAsText(1) # Field that is the unique id for every extent poly
    wetlands = arcpy.GetParameterAsText(2) # Wetland polygon feature class
    top_outfolder = arcpy.GetParameterAsText(3) # Output folder
    wetlands_in_zones(infolder, idfield, wetlands, top_outfolder)

def test():
    arcpy.env.overwriteOutput = True
    infolder = '' # Workspace with zone feature classes
    idfield = '' # Field that is the unique id for every extent poly
    wetlands = '' # Wetland polygon feature class
    top_outfolder = '' # Output folder
    wetlands_in_zones(infolder, idfield, wetlands, top_outfolder)

if __name__ == '__main__':
    main()




