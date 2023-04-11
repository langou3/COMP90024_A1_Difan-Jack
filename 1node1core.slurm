#!/bin/bash
#SBATCH --job-name=Jack&Difan_1&1
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --mail-user=difanw@student.unimelb.edu.au
#SBATCH --mail-type=ALL
#SBATCH --output=Outputs/slurm.%N.%j.out
#SBATCH --error=Outputs/slurm.%N.%j.err


module purge
module load foss/2019b
module load python/3.7.4
module load mpi4py/3.0.2-timed-pingpong

mkdir virtualenv
virtualenv ~/virtualenv/python3.7.4
source ~/virtualenv/python3.7.4/bin/activate
pip install json
pip install time
pip install re
pip install os
pip install collections
pip install pandas



srun -n 1 python3 process.py
deactivate
##Job monitor command to list the resource usage
my-job-stats -a -n -s
