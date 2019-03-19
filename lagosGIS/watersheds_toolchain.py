from os import path
import os
from datetime import datetime
from zipfile import ZipFile
import arcpy
import nhdplushr_tools as nt

# Locations of main directories (unique to machine)

# this is the result of the lakes_in_the_us/doit.py
LAGOS_LAKES = r'C:\Users\smithn78\Dropbox\CL_HUB_GEO\LAGOS_US_GIS_Data_v0.5.gdb\Lakes\LAGOS_US_All_Lakes_1ha'

# straight as downloaded from web in mid-March 2019
NHDPLUS_ZIPPED_DIR = 'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution\Zipped'
NHDPLUS_UNZIPPED_DIR = 'F:\Continental_Limnology\Data_Downloaded\NHDPlus_High_Resolution\Unzipped_Original'

# a directory wherever you want to store the outputs
# each subregion will have its own geodatabase created and saved

OUTPUTS_PARENT_DIR = 'D:\Continental_Limnology\Data_Working\Tool_Execution\Watersheds'

TOOL_ORDER = ('update_grid_codes', 'add_lake_seeds', 'delineate_catchments', 'interlake_watersheds', 'network_watersheds')

class Paths:
    """
    Define job control paths for the 4-digit HUC4.

    :param str huc4: 4-digit HUC4 for the geodatabase to be processed.

    """
    def __init__(self, huc4):
        self.huc4 = huc4
        self.gdb_zip = path.join(NHDPLUS_ZIPPED_DIR, 'NHDPLUS_H_{}_HU4_GDB.zip'.format(huc4))
        self.rasters_zip = path.join(NHDPLUS_ZIPPED_DIR, 'NHDPLUS_H_{}_HU4_RASTER.7z'.format(huc4))

        # NHD items that don't exist at start
        self.gdb = path.join(NHDPLUS_UNZIPPED_DIR, 'NHDPLUS_H_{}_HU4_GDB.gdb'.format(huc4))
        self.rasters_dir = path.join(NHDPLUS_UNZIPPED_DIR, 'HRNHDPlusRasters{}'.format(huc4))
        self.waterbody = path.join(self.gdb, 'NHDWaterbody')
        self.catseed = path.join(self.rasters_dir, 'catseed.tif')
        self.fdr = path.join(self.rasters_dir, 'fdr.tif')

        # output items that don't exist at start
        self.out_gdb = path.join(OUTPUTS_PARENT_DIR, 'watersheds_{}.gdb'.format(huc4))
        self.gridcode = path.join(self.out_gdb, 'lagos_gridcode_{}'.format(huc4))
        self.lagos_catseed = path.join(self.out_gdb, 'lagos_catseed_{}'.format(huc4))
        self.local_catchments = path.join(self.out_gdb, 'lagos_catchments_{}'.format(huc4))
        self.iws_sheds = path.join(self.out_gdb, 'lagos_interlake_watersheds_{}'.format(huc4))
        self.network_sheds = path.join(self.out_gdb, 'lagos_network_watersheds_{}'.format(huc4))

    def exist(self):
        """Check whether NHDPlus data available locally in order to proceed."""
        return os.exists(self.gdb_zip) and os.exists(self.rasters_zip)

    def test_zips(self):
        """Return logical indicating whether initial paths exist."""
        test_gdb = ZipFile(self.gdb_zip, 'r').testzip()
        if test_gdb:
            print('{} has a bad file: {}'.format(self.gdb_zip, test_gdb))

        test_rasters = ZipFile(self.rasters_zip, 'r').testzip()
        if test_rasters:
            print('{} has a bad file: {}'.format(self.rasters_zip, test_rasters))

        if test_gdb or test_rasters:
            return False
        else:
            return True

    def unzip(self):
        with ZipFile(self.gdb_zip, 'r') as z:
            z.extractall(NHDPLUS_UNZIPPED_DIR)

        if not os.exists(self.rasters_dir):
            os.mkdir(self.rasters_dir)
        with ZipFile(self.rasters_zip, 'r') as z:
            for r in ['catseed.tif', 'fdr.tif']:
                z.extract(r, self.rasters_dir)

    def log(self):
        """Format a comma-separated line for recording paths to logging file."""
        items = (self.huc4,
                 self.gdb_zip,
                 self.rasters_zip,
                 'NHDWaterbody; catseed.tif; fdr.tif',
                 LAGOS_LAKES,
                 self.gridcode,
                 self.lagos_catseed,
                 self.local_catchments,
                 self.iws_sheds,
                 self.network_sheds,
                 'add_waterbody_nhdpid(); update_grid_codes(); add_lake_seeds(); delineate_catchments();')
        return ','.join(items)

def run(paths, last_tool='network_watersheds'):

    stop_index = TOOL_ORDER.index(last_tool)
    # Check that we have the data, otherwise log only the HUC4 (empty line) and skip
    if not paths.exist():
        # TODO: Write only the HU4 number to the log file an
        pass

    if not os.exists(paths.out_gdb):
        os.mkdir(paths.out_gdb)

    start_time = datetime.now()
    paths.unzip()

    # If the tool output doesn't exist yet, and the job control agrees it should be run, try running.
    # If the tool fails, continue after logging the error to the CSV.
    nt.add_waterbody_nhdpid(paths.waterbody, LAGOS_LAKES)
    if not arcpy.Exists(paths.gridcode) and stop_index > 0:
        try:
            nt.update_grid_codes(paths.gdb, paths.gridcode)
        except Exception as e:
            print(e)
            # TODO: Log failure!
            stop_index = 1
            raise
    if not arcpy.Exists(paths.lagos_catseed) and stop_index > 1:
        try:
            nt.add_lake_seeds(paths.catseed, paths.gridcode, LAGOS_LAKES, paths.lagos_catseed)
        except Exception as e:
            print(e)
            # TODO: Log failure!
            stop_index = 2
            raise
    if not arcpy.Exists(paths.local_catchments) and stop_index > 2:
        try:
            nt.delineate_catchments(paths.fdr, paths.lagos_catseed, paths.gridcode, paths.local_catchments)
        except Exception as e:
            print(e)
            # TODO: Log failure!
            stop_index = 3
            raise
    if not arcpy.Exists(paths.iws_sheds) and stop_index > 3:
        try:
            nt.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.iws_sheds, 'interlake')
        except Exception as e:
            print(e)
            # TODO: Log failure!
            stop_index = 4
            raise
    if not arcpy.Exists(paths.network_sheds) and stop_index == 4:
        try:
            nt.aggregate_watersheds(paths.local_catchments, paths.gdb, LAGOS_LAKES, paths.network_sheds, 'network')
        except Exception as e:
            print(e)
            # TODO: Log failure!
            raise


# TODO: exceptions and logging effects
huc4_list = ''
for huc4 in huc4_list:
    try:
        run(huc4)
    except:
        continue