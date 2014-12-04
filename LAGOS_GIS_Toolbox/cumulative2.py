import os, re, shutil
import arcpy
import csiutils as cu

from interlake2 import aggregate_watersheds

def test():
    watersheds_fc = 'C:/GISData/Scratch/new_watersheds_nov27.gdb/huc05030104_final_watersheds'
    nhd_gdb = r'E:\nhd\fgdb\NHDH0503.gdb'
    pour_dir =  r'C:\GISData\Scratch\new_pourpoints\pourpoints0503'
    output_fc = 'C:/GISData/Scratch/Scratch.gdb/CUMULATIVE_TEST'
    aggregate_watersheds(watersheds_fc, nhd_gdb, pour_dir,
                            output_fc, mode = 'cumulative')
def main():
    watersheds_fc = arcpy.GetParameterAsText(0)
    nhd_gdb = arcpy.GetParameterAsText(2)
    pour_dir =  arcpy.GetParameterAsText(3)
    output_fc = arcpy.GetParameterAsText(4)
    aggregate_watersheds(watersheds_fc, nhd_gdb, pour_dir,
                            output_fc, mode = 'cumulative')

if __name__ == '__main__':
    main()
