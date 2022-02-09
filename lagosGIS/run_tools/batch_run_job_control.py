# filename: batch_run_job_control.py
# author: Nicole J Smith
# version: 2.0
# LAGOS module(s): all
# tool type: code journal, internal use, batch run

import read_job_control as rjc

va = ['Arg1', 'Arg3', 'Arg6']
pva = ['Arg1', 'Arg3']
job_csv = '../geo_job_control.csv'

rjc.read_job_control(job_csv)