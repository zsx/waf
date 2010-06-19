#! /usr/bin/env python
# encoding: utf-8
# DC 2008
# Thomas Nagy 2010 (ita)

from waflib.extras import fortran
from Configure import conf

@conf
def find_gfortran(conf):
	conf.find_program('gfortran', var='FC')
	conf.env.FC_NAME = 'GFORTRAN'

@conf
def gfortran_flags(conf):
	v = conf.env
	v['fshlib_FCFLAGS']   = ['-fPIC']
	v['FORTRANMODFLAG']  = ['-M', ''] # template for module path

def configure(conf):
	conf.find_gfortran()
	conf.find_ar()
	conf.fc_flags()
	conf.gfortran_flags()

