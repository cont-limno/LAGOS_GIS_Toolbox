import os
import sys

script, raster_dir, qsub_path, tool, walltime, taudem_dir = sys.argv
def create_squb(raster_dir, qsub_path, tool = ('pitremove', 'd8flowdir'), walltime = '0:30:00', taudem_dir = ''):
    tif_list = []
    for root, dirs, files in os.walk(raster_dir):
        for f in files:
            if f.endswith('.tif'):
                if 'fel' not in f and 'sd8' not in f and 'p.tif' not in f:
                    tif_list.append(os.path.join(root, name))

    for tif in tif_list:
        with open(qsub_path, 'a') as f:
            name = os.path.splitext(os.path.basename(tif))[0]
            f.write("""#!/bin/bash --login
            #PBS -j oe
            #PBS -l walltime={0},nodes=8:ppn=1,mem=8gb,feature=gbe
            #PBS -N {1}

            file={2}
            echo ${PBS_JOBID} ${file}
            time mpiexec -n 8 {3} ${file}
            qstat -f
            """.format(walltime, name, tif, tool))

##            os.system('qsub {0}'.format(qsub_path))



def main():
    pass

if __name__ == '__main__':
    main()
