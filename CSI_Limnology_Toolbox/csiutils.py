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

