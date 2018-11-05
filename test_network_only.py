import os
import sys
import arcpy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import lagosGIS

arcpy.env.overwriteOutput = True

__all__ = ['lake_from_to']

#HARD_CODED
test_data_gdb = r'D:\Continental_Limnology\Data_Downloaded\National_Hydrography_Dataset\Unzipped_Original\NHD_H_0405_GDB.gdb'

def lake_from_to(output_table):
    lagosGIS.lake_from_to(test_data_gdb, output_table)
