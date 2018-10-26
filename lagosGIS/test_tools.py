#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      smithn78
#
# Created:     20/12/2013
# Copyright:   (c) smithn78 2013
# Licence:     <your licence>
#-------------------------------------------------------------------------------
# testing
import time
from arcpy import env

import interlake2 as tool

def main():
    t = time.time()
    env.overwriteOutput = True
    print("Starting test at {}.".format(time.asctime()))
    tool.test()
    time_took = time.time() - t
    print("Tool took %.1f seconds to complete" % time_took)

if __name__ == '__main__':
    main()

