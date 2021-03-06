#! /usr/bin/env python
# encoding: utf-8
# DC 2008
# Thomas Nagy 2010 (ita)

from waflib.extras import fc
from waflib.Configure import conf

@conf
def find_ifort(conf):
	conf.find_program('ifort', var='FC')
	conf.env.FC_NAME = 'IFORT'

def configure(conf):
	conf.find_ifort()
	conf.find_ar()
	conf.fc_flags()

