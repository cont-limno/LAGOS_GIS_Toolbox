#-------------------------------------------------------------------------------
# Name:        csiutils
# Purpose: To provide a number of small functions called repeatedly throughout the CSI Limnology toolbox that users do not need to access, only developers
#
# Author:      CSI
#
# Created:     19/12/2013

#-------------------------------------------------------------------------------
import arcpy, os

def main():
    pass

if __name__ == '__main__':
    main()

def multi_msg(message):
    """Prints given string message no matter where script is executed: in Python
    interpreter and ArcGIS geoprocessing dialog using
    print statement, also ArcGIS Results window (for background processing) or geoprocessing dialog using
    arcpy.AddMessage"""
    print(message)
    arcpy.AddMessage(message)

def cleanup(intermediate_items_list):
    """Safely deletes intermediate outputs using ArcGIS method only if they exist. Accepts a path expressed as a string or a list/tuple of paths. Uses ArcGIS existence test so geodatabase items are okay in addition to ordinary OS paths."""
    if type(intermediate_items_list) is str:
        intermediate_items_list = [intermediate_items_list]
    for item in intermediate_items_list:
        if arcpy.Exists(item):
            arcpy.Delete_management(item)

