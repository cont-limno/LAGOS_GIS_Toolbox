# Filename : LakeClass.py
# Author : Scott Stopyak, Geographer, Michigan State University
# Purpose : Classify lakes according to their connectivity to the hydrologic network using only NHD as input.

import os
import arcpy
import shutil

# User input:
nhd = arcpy.GetParameterAsText(0)
arcpy.env.workspace = nhd
outfolderinput = arcpy.GetParameterAsText(1)

# Environments:
arcpy.ResetEnvironments()
arcpy.env.overwriteOutput = "TRUE"
arcpy.RefreshCatalog(outfolderinput)

# Local variables:
nhdflowline = nhd + "\\" + "Hydrography" + "\\" + "NHDFlowline"
nhdjunction = nhd + "\\" + "Hydrography" + "\\" + "HYDRO_NET_Junctions"
nhdwaterbody = nhd + "\\" + "Hydrography" + "\\" + "NHDWaterbody"
network = nhd + "\\" + "Hydrography" + "\\" + "HYDRO_NET"
fd = nhd + "\\" + "Hydrography"

# Naming convention that inherits name from input NHD gdb.
subregion_number = os.path.basename(nhd)
nhdsubregion = subregion_number[4:8]

# Create output subdirectory
if not os.path.exists(os.path.join(outfolderinput, nhdsubregion)):
    os.mkdir(os.path.join(outfolderinput, nhdsubregion))

outfolder = os.path.join(outfolderinput, nhdsubregion)   

# Get lakes, ponds and reservoirs over a hectare.

arcpy.MakeFeatureLayer_management(nhdwaterbody, os.path.join(outfolder, "csiwaterbody.lyr"),'''"AreaSqKm" >=0.01 AND\
("FCode" = 39000 OR "FCode" = 39004 OR "FCode" = 39009 OR "FCode" = 39010 OR "FCode" = 39011 OR "FCode" = 39012 OR\
"FCode" = 43600 OR "FCode" = 43613 OR "FCode" = 43615 OR "FCode" = 43617 OR "FCode" = 43618 OR "FCode" = 43619 OR\
"FCode" = 43621 OR ("FCode" = 43601 AND "AreaSqKm" >=0.1 ))''')
                                  
csiwaterbody_lyr = os.path.join(outfolder, "csiwaterbody.lyr")
arcpy.CopyFeatures_management(csiwaterbody_lyr, os.path.join(outfolder, "csiwaterbody.shp"))
csiwaterbody = os.path.join(outfolder, "csiwaterbody.shp")

# Get lakes, ponds and reservoirs over 10 hectares.
arcpy.MakeFeatureLayer_management(nhdwaterbody, os.path.join(outfolder, "csiwaterbody10ha.lyr"),\
                                  """"AreaSqKm" >= 0.1 AND ( "FType" = 390 OR "FType" = 436 )""")
csiwaterbody10ha_lyr = os.path.join(outfolder, "csiwaterbody10ha.lyr")
arcpy.CopyFeatures_management(csiwaterbody10ha_lyr, os.path.join(outfolder, "csiwaterbody10ha.shp"))
csiwaterbody10ha = os.path.join(outfolder, "csiwaterbody10ha.shp")
arcpy.AddMessage("Defined CSI lakes.")

# Make junction shapefile and layer.
arcpy.FeatureClassToShapefile_conversion(nhdjunction, outfolder)
arcpy.RefreshCatalog(outfolder)
csijunction =  os.path.join(outfolder, "HYDRO_NET_Junctions.shp")
arcpy.MakeFeatureLayer_management(csijunction, os.path.join(outfolder, "csijunction.lyr"))
csijunction_lyr = os.path.join(outfolder, "csijunction.lyr")

# Make dangle points at end of nhdflowline
arcpy.FeatureClassToShapefile_conversion(nhdflowline, outfolder)
flowline1 = os.path.join(outfolder, "NHDFlowline.shp")
arcpy.FeatureVerticesToPoints_management(flowline1,os.path.join(outfolder, "dangles.shp"), "DANGLE")
dangles = os.path.join(outfolder, "dangles.shp")

# Isolate start dangles from end dangles.
arcpy.FeatureVerticesToPoints_management(flowline1,os.path.join(outfolder, "start.shp"), "START")
start = os.path.join(outfolder, "start.shp")
arcpy.MakeFeatureLayer_management(dangles, os.path.join(outfolder, "dangles.lyr"))
dangles_lyr = os.path.join(outfolder, "dangles.lyr")
arcpy.SelectLayerByLocation_management(dangles_lyr, "ARE_IDENTICAL_TO", start)
arcpy.CopyFeatures_management(dangles_lyr, os.path.join(outfolder, "startdangles.shp"))
startdangles = os.path.join(outfolder, "startdangles.shp")
arcpy.AddMessage("Found source area nodes.")

# Get junctions from lakes >= 10 hectares.
arcpy.SelectLayerByLocation_management(csijunction_lyr, "INTERSECT", csiwaterbody10ha, "", "NEW_SELECTION")
arcpy.CopyFeatures_management(csijunction_lyr, os.path.join(outfolder, "csijunction10ha.shp"))
csijunction10ha = os.path.join(outfolder, "csijunction10ha.shp")
arcpy.AddMessage("Found lakes >= 10 ha.")

# Make points shapefile and layer at flowline vertices to act as potential flags and/or barriers.
arcpy.AddMessage("Tracing...")
arcpy.FeatureVerticesToPoints_management(flowline1, os.path.join(outfolder, "vertices1.shp"), "MID")
vertices = os.path.join(outfolder, "vertices1.shp")
arcpy.MakeFeatureLayer_management(vertices, os.path.join(outfolder, "vertices.lyr"))
vertices_lyr = os.path.join(outfolder, "vertices.lyr")

# Get vertices that are not coincident with 10 hectare lake junctions.
arcpy.SelectLayerByLocation_management(vertices_lyr, "INTERSECT", csijunction10ha, "", "NEW_SELECTION")
arcpy.SelectLayerByLocation_management(vertices_lyr, "INTERSECT", csijunction10ha, "", "SWITCH_SELECTION")
arcpy.CopyFeatures_management(vertices_lyr, os.path.join(outfolder, "non10vertices.shp"))
non10vertices = os.path.join(outfolder, "non10vertices.shp")

# Get junctions that are not coincident with 10 hectare lake junctions.
arcpy.SelectLayerByLocation_management(csijunction_lyr, "INTERSECT", csijunction10ha, "", "NEW_SELECTION")
arcpy.SelectLayerByLocation_management(csijunction_lyr, "INTERSECT", csijunction10ha, "", "SWITCH_SELECTION")
arcpy.CopyFeatures_management(csijunction_lyr, os.path.join(outfolder, "non10junctions.shp"))
non10junctions = os.path.join(outfolder, "non10junctions.shp")

# Merge non10vertices with non10junctions for a new shp and lyr.
arcpy.Merge_management([non10junctions, non10vertices], os.path.join(outfolder,  "non10merged.shp")) 
non10merged = os.path.join(outfolder,  "non10merged.shp")
arcpy.MakeFeatureLayer_management(non10merged, os.path.join(outfolder, "non10merged.lyr"))
non10merged_lyr = os.path.join(outfolder, "non10merged.lyr")

# For tracing barriers, select non10merged points that don't intersect a 10 ha lake.
arcpy.SelectLayerByLocation_management(non10merged_lyr, "INTERSECT", csiwaterbody10ha, "", "NEW_SELECTION")
arcpy.CopyFeatures_management(non10merged_lyr, os.path.join(outfolder, "non10barriers.shp"))
non10barriers = os.path.join(outfolder, "non10barriers.shp")

# Trace1-Trace downstream to first non10hajunction starting from csijunction10ha flag points.
arcpy.TraceGeometricNetwork_management(network, "trace1", csijunction10ha,\
                                       "TRACE_DOWNSTREAM", non10barriers)

# Save trace1 flowlines and junctions to layers on disk.
arcpy.SaveToLayerFile_management("trace1\HYDRO_NET_Junctions", os.path.join(outfolder, "trace1junctions.lyr"))
trace1junctions_lyr = os.path.join(outfolder, "trace1junctions.lyr")
arcpy.SaveToLayerFile_management("trace1\NHDFlowline", os.path.join(outfolder, "trace1flowline.lyr"))
trace1flowline_lyr = os.path.join(outfolder, "trace1flowline.lyr")

# Select vertice midpoints that intersect trace1 flowlines selection for new flags for trace2.
arcpy.SelectLayerByLocation_management(vertices_lyr, "INTERSECT", trace1flowline_lyr, "", "NEW_SELECTION")
arcpy.CopyFeatures_management(vertices_lyr, os.path.join(outfolder, "trace2flags.shp"))
trace2flags = os.path.join(outfolder, "trace2flags.shp")

# Trace2-Trace downstream from midpoints of flowlines that intersect the selected flowlines from trace1.
arcpy.TraceGeometricNetwork_management(network, "trace2", trace2flags,"TRACE_DOWNSTREAM")

# Save trace1 flowlines and junctions to layers and then shapes on disk.
arcpy.SaveToLayerFile_management("trace2\HYDRO_NET_Junctions", os.path.join(outfolder, "trace2junctions.lyr"))
trace2junctions_lyr = os.path.join(outfolder, "trace2junctions.lyr")
arcpy.SaveToLayerFile_management("trace2\NHDFlowline", os.path.join(outfolder, "trace2flowline.lyr"))
trace2flowline_lyr = os.path.join(outfolder, "trace2flowline.lyr")
arcpy.AddMessage("Done tracing.")

# Select csiwaterbody that intersect trace2junctions
arcpy.AddMessage("Beginning connectivity attribution...")
arcpy.SelectLayerByLocation_management(csiwaterbody_lyr, "INTERSECT", trace2junctions_lyr, "", "NEW_SELECTION")
arcpy.CopyFeatures_management(csiwaterbody_lyr, os.path.join(outfolder, "STLA_Lakes.shp"))
stla_lakes = os.path.join(outfolder, "STLA_Lakes.shp")

# Make shapefile for seepage lakes. (Ones that don't intersect flowlines)
arcpy.SelectLayerByLocation_management(csiwaterbody_lyr, "INTERSECT", nhdflowline, "", "NEW_SELECTION")
arcpy.SelectLayerByLocation_management(csiwaterbody_lyr, "INTERSECT", nhdflowline, "", "SWITCH_SELECTION")
arcpy.CopyFeatures_management(csiwaterbody_lyr, os.path.join(outfolder, "SE_Lakes.shp"))
se_lakes = os.path.join(outfolder, "SE_Lakes.shp")

# Get headwater lakes.
arcpy.SelectLayerByLocation_management(csiwaterbody_lyr, "INTERSECT", startdangles, "", "NEW_SELECTION")
arcpy.CopyFeatures_management(csiwaterbody_lyr, os.path.join(outfolder, "HW_Lakes.shp"))
hw_lakes = os.path.join(outfolder, "HW_Lakes.shp")

# Get stream drainage lakes.
arcpy.SelectLayerByLocation_management(csiwaterbody_lyr, "ARE_IDENTICAL_TO", stla_lakes, "", "NEW_SELECTION")
arcpy.SelectLayerByLocation_management(csiwaterbody_lyr, "ARE_IDENTICAL_TO", se_lakes, "", "ADD_TO_SELECTION")
arcpy.SelectLayerByLocation_management(csiwaterbody_lyr, "ARE_IDENTICAL_TO", hw_lakes, "", "ADD_TO_SELECTION")
arcpy.SelectLayerByLocation_management(csiwaterbody_lyr, "","", "", "SWITCH_SELECTION")
arcpy.CopyFeatures_management(csiwaterbody_lyr, os.path.join(outfolder, "ST_Lakes.shp"))
st_lakes = os.path.join(outfolder, "ST_Lakes.shp")

# Create a new field for connectivity classification in each class shape.
typelist = [stla_lakes, se_lakes, st_lakes, hw_lakes]
for type in typelist:
    arcpy.AddField_management(type, "Connection", "TEXT")

# Calculate Class fields  
arcpy.CalculateField_management(stla_lakes, "Connection", '''"%s" % ("DR_LakeStream")''', "PYTHON")
arcpy.CalculateField_management(se_lakes, "Connection", '''"%s" % ("Isolated")''', "PYTHON")
arcpy.CalculateField_management(st_lakes, "Connection", '''"%s" % ("DR_Stream")''', "PYTHON")
arcpy.CalculateField_management(hw_lakes, "Connection", '''"%s" % ("Headwater")''', "PYTHON")
arcpy.AddMessage("Lake connectivity attribution is complete.")

# Merge lake types to a single shape projected to albers.
albers = arcpy.SpatialReference()
albers.factoryCode = 102039
albers.create()
arcpy.env.outputCoordinateSystem = albers
arcpy.Merge_management(typelist, os.path.join(outfolder, "CSILakes_" + nhdsubregion + ".shp"))
arcpy.AddMessage("Projected dataset to EPSG 102039.")

# Clean up intermediate outputs.
arcpy.env.workspace = outfolder
arcpy.RefreshCatalog(outfolder)
for root, dirs, files in os.walk(outfolder):
    for filename in files:
        if not filename.startswith("CSILakes_"):
            try:
                filepath = os.path.join(root, filename)
                os.remove(filepath)
            except WindowsError:
                pass
arcpy.RefreshCatalog(outfolder)
arcpy.AddMessage("Cleaned up intermediate data.")
arcpy.AddMessage("Lake Connectivity classification is complete.")
    


