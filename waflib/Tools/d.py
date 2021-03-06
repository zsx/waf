#!/usr/bin/env python
# encoding: utf-8
# Carlos Rafael Giani, 2007 (dv)
# Thomas Nagy, 2007-2010 (ita)

import os, sys
from waflib import Utils, Task, Errors
from waflib.TaskGen import taskgen_method, feature, after, before, extension
from waflib.Configure import conf
from waflib.Tools.ccroot import link_task
from waflib.Tools import d_scan, d_config
from waflib.Tools.ccroot import link_task, stlink_task

class d(Task.Task):
	color   = 'GREEN'
	run_str = '${D} ${DFLAGS} ${DINC_ST:INCPATHS} ${D_SRC_F}${SRC} ${D_TGT_F}${TGT}'
	scan    = d_scan.scan

	def exec_command(self, *k, **kw):
		"""dmd wants -of stuck to the file name"""
		if isinstance(k[0], list):
			lst = k[0]
			for i in range(len(lst)):
				if lst[i] == '-of':
					del lst[i]
					lst[i] = '-of' + lst[i]
					break
		return super(d, self).exec_command(*k, **kw)

class d_with_header(d):
	run_str = '${D} ${DFLAGS} ${DINC_ST:INCPATHS} ${D_HDR_F}${TGT[1].bldpath()} ${D_SRC_F}${SRC} ${D_TGT_F}${TGT[0].bldpath()}'

class d_header(Task.Task):
	color   = 'BLUE'
	run_str = '${D} ${D_HEADER} ${SRC}'


class dprogram(link_task):
	run_str = '${D_LINKER} ${DLNK_SRC_F}${SRC} ${DLNK_TGT_F}${TGT} ${RPATH_ST:RPATH} ${STLIB_MARKER} ${STLIBPATH_ST:STLIBPATH} ${STLIB_ST:STLIB} ${SHLIB_MARKER} ${LIBPATH_ST:LIBPATH} ${LIB_ST:LIB} ${LINKFLAGS}'
	inst_to = '${BINDIR}'
	chmod   = Utils.O755
	def exec_command(self, *k, **kw):
		"""dmd wants -of stuck to the file name"""
		# TODO duplicate, but do we really want multiple inheritance?
		if isinstance(k[0], list):
			lst = k[0]
			for i in range(len(lst)):
				if lst[i] == '-of':
					del lst[i]
					lst[i] = '-of' + lst[i]
					break
		return super(dprogram, self).exec_command(*k, **kw)

class dshlib(dprogram):
	inst_to = '${LIBDIR}'

class dstlib(stlink_task):
	pass

@extension('.d', '.di', '.D')
def d_hook(self, node):
	"""set 'generate_headers' to True on the task generator to get .di files as well as .o"""
	if getattr(self, 'generate_headers', None):
		task = self.create_compiled_task('d_with_header', node)
		header_node = node.change_ext(self.env['DHEADER_ext'])
		task.outputs.append(header_node)
	else:
		task = self.create_compiled_task('d', node)
	return task

@taskgen_method
def generate_header(self, filename, install_path=None):
	"""see feature request #104 - TODO the install_path is not used"""
	try:
		self.header_lst.append([filename, install_path])
	except AttributeError:
		self.header_lst = [[filename, install_path]]

@feature('d')
def process_header(self):
	for i in getattr(self, 'header_lst', []):
		node = self.path.find_resource(i[0])
		if not node:
			raise Errors.WafError('file %r not found on d obj' % i[0])
		self.create_task('d_header', node, node.change_ext('.di'))

