# big run of all the raster data at all the extents
import os, time
import arcpy
from arcpy import env
import zonal_tabarea

# leave this function alone if you're just trying to reuse the script
def batch_raster_attribution(all_rasters, all_extents, zone_field, out_gdb,
                            is_thematic_list, search_gdbs = [], log_file = ''):
    """Runs a lot of Zonal Attribution for Raster Data (NON OVERLAPPING) at once.
    INPUTS
    all_rasters: a list of all the rasters you would like in the batch run
    all_extents: a list of all the NON-OVERLAPPING extents/zones you would like
                 in the batch run. They mu
    out_gdb: The geodatabase the output tables will be written to
    search_gdbs: (OPTIONAL) A list of geodatabases with previously created,
                 VALID output tables in them. If a table with the name of the
                 planned output table already exists in one of these places,
                 will not rerun the calculation at this time. If you want to
                 replace tables with the same name, leave this blank or
                 delete/rename the old invalid table"""
    search_gdbs.append(out_gdb)

    # first check that everything exists and warn the user
    all_paths = all_rasters + all_extents + [out_gdb] + search_gdbs
    all_paths_exist = map(lambda x: arcpy.Exists(x), all_paths)
    if any(all_paths_exist):
        for i, x in enumerate(all_paths_exist):
            if x is False:
                print("THE TOOL CANNOT RUN!")
                print("Check path {0}". format(all_paths[i]))

    if all(all_paths_exist):
        # then do the rest of the tool
        print("All paths were verified to exist.")
        for e in all_extents:
            e_short = os.path.basename(e)
            for r, is_thematic in zip(all_rasters, is_thematic_list):
                r_short = os.path.splitext(os.path.basename(r))[0]

                out_table_short = '{0}_{1}'.format(e_short, r_short)

                # test for previously calculated table existence
                is_previous_output = False
                exists_candidates = [os.path.join(gdb, out_table_short) for
                                            gdb in search_gdbs]
                if any(map(lambda x: arcpy.Exists(x), exists_candidates)):
                    is_previous_output = True
##
##                for candidate in previous_table_candidates:
##                    if arcpy.Exists(candidate):
##                        is_previous_output = True

                # if there is no previous table do the calculation
                out_table = os.path.join(out_gdb, out_table_short)
                if is_previous_output is False:
                    t = time.time()
                    localtime = time.asctime(time.localtime(t))
                    start_msg = "Calculating table {0} starting at {1}.".format(
                            os.path.basename(out_table), localtime)
                    print(start_msg)
                    if log_file:
                        with open(log_file, 'a') as f:
                            f.write(start_msg + '\n')
                    try:
                        zonal_tabarea.stats_area_table(e, zone_field, r, out_table,
                                                    is_thematic)
                        elapsed_time = (time.time() - t)/60
                        finish_msg = "Table {0} completed in {1} minutes.".format(
                                os.path.basename(out_table), elapsed_time)
                        print(finish_msg)
                        if log_file:
                            with open(log_file, 'a') as f:
                                f.write(finish_msg + '\n')

                    except Exception as e:
                        fail_msg = "Could not create table {0}".format(out_table)
                        print(fail_msg)
                        print(e.message)
                        if log_file:
                            with open(log_file, 'a') as f:
                                f.write(fail_msg + '\n')
                                f.write(e.message + '\n')
                        continue
                else:
                    exists_msg = "There is already a table for {0}".format(
                            os.path.basename(out_table))
                    print(exists_msg)
                    if log_file:
                        with open(log_file, 'a') as f:
                            f.write(exists_msg + '\n')
                    continue


# all the variables in capitals (i.e. constant variables) should be changed
# by the user

# make the list of all_rasters any way that you like

# PRISM
##normal_dir = 'E:/Attribution_Rasters_2013/prism/normals'
##env.workspace = normal_dir
##prism_list = [os.path.join(normal_dir, r) for r in arcpy.ListRasters('PRISM*annual.tif')] # annuals only
##prism_dirs = [os.path.join('E:/Attribution_Rasters_2013/prism', d) for d in
##                ['ppt', 'tmean', 'tmin', 'tmax']]
##for pdir in prism_dirs:
##    env.workspace = pdir
##    prism_list.extend([os.path.join(pdir, r) for r in arcpy.ListRasters('us*.tif')]) # annuals only
##
###GROUNDWATER
##gw_dir = 'E:/Attribution_Rasters_2013/Groundwater'
##env.workspace = gw_dir
##groundwater_list = [os.path.join(gw_dir, r) for r in arcpy.ListRasters('*')]
##
###LULC
##lulc_list = ['E:/Attribution_Rasters_2013/MRLC/nlcd1992.tif',
##            'E:/Attribution_Rasters_2013/MRLC/nlcd2001.tif',
##            'E:/Attribution_Rasters_2013/MRLC/nlcd2006.tif',
##            'E:/Attribution_Rasters_2013/MRLC/nlcd2011.tif']

#canopy and impervious
other_mrlc_list = ['E:/Attribution_Rasters_2013/MRLC/impervious2001.tif',
                    'E:/Attribution_Rasters_2013/MRLC/impervious2006.tif',
                    'E:/Attribution_Rasters_2013/MRLC/impervious2011.tif',
                    'E:/Attribution_Rasters_2013/MRLC/canopy2001.tif',
                    'E:/Attribution_Rasters_2013/MRLC/canopy2011.tif'
                    ]

### cropland
##crop_dir = r'E:\Attribution_Rasters_2013\Cropland'
##env.workspace = crop_dir
##cropland_list = [os.path.join(crop_dir, r) for r in  arcpy.ListRasters('crops*tif')]
##
### nadp
##nadp_dirs = [ r'E:\Attribution_Rasters_2013\NewNADP\NO3',
##            r'E:\Attribution_Rasters_2013\NewNADP\SO4',
##            r'E:\Attribution_Rasters_2013\NewNADP\TotalN']
##nadp_list = []
##for ndir in nadp_dirs:
##    env.workspace = ndir
##    nadp_list.extend([os.path.join(ndir, r) for r in arcpy.ListRasters('dep*0.tif')]) # 90, 2000, 2010
##    nadp_list.extend([os.path.join(ndir, r) for r in arcpy.ListRasters('dep*5.tif')]) # 85, 95, 2005
##
##others = []

# make however you want, ideally order from coarse to fine resolution
##ALL_RASTERS = (nadp_list + groundwater_list + prism_list + cropland_list +
##                lulc_list + other_mrlc_list + others)

ALL_RASTERS = (other_mrlc_list)

# make list of is_thematic True/False values however you want,
# I know my only thematic rasters are LULC or cropland rasters so using a test
##THEMATIC_FLAGS = map(lambda x: x in lulc_list or x in cropland_list, ALL_RASTERS)
THEMATIC_FLAGS = [False] * len(ALL_RASTERS)


MGDB = 'C:/GISData/Master_Geodata/MasterGeodatabase2014_ver3.gdb/US_Extents'
ALL_EXTENTS = [os.path.join(MGDB, e) for e in ['HU12', 'HU8', 'HU4', 'EDU', 'COUNTY', 'STATE']]

OUT_GDB = r'C:\GISData\Attribution_Sept2014_FIXES.gdb'
SEARCH_GDBS = []

LOG_FILE = 'C:/Users/smithn78/CSI_Processing/batch_rasters_sept21.txt'

# go ahead and do it! leave this alone too if you're reusing the script
batch_raster_attribution(ALL_RASTERS, ALL_EXTENTS, 'ZoneID', OUT_GDB,
                            THEMATIC_FLAGS, [], LOG_FILE)
