#! /usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005 (ita)

"Environment representation"

import os, sys, string, types, copy
import Params, Utils
from Utils import Undefined
from Params import debug, error, fatal, warning

g_idx = 0
class Environment(object):
	"""A safe-to-use dictionary, but do not attach functions to it please (break cPickle)
	An environment instance can be stored into a file and loaded easily
	"""
	def __init__(self):
		global g_idx
		self.m_idx = g_idx
		g_idx += 1
		self.m_table={}
		self.m_var_cache={}

		# set the prefix once and for everybody on creation (configuration)
		self.m_table['PREFIX'] = Params.g_options.prefix

	def __contains__(self, key):
		return key in self.m_table

	def set_variant(self, name):
		self.m_table['_VARIANT_'] = name

	def variant(self):
		return self.m_table.get('_VARIANT_', 'default')

	def copy(self):
		return self.deepcopy()
		#newenv = Environment()
		#newenv.m_table = self.m_table.copy() # TODO how to avoid deep copies ? see issue #86
		#return newenv

	def deepcopy(self):
		newenv = Environment()
		newenv.m_table = copy.deepcopy(self.m_table)
		return newenv

	def __str__(self):
		return "environment table\n"+str(self.m_table)

	def __getitem__(self, key):
		r = self.m_table.get(key, None)
		if r is not None:
			return r
		return Params.g_globals.get(key, [])

	def __setitem__(self, key, value):
		self.m_table[key] = value

	def get_flat(self, key):
		s = self.m_table.get(key, '')
		if not s: return ''
		if type(s) is types.ListType: return ' '.join(s)
		else: return s

	def append_value(self, var, value):
		if type(value) is types.ListType: val = value
		else: val = [value]
		#print var, self[var]
		try: self.m_table[var] = self[var] + val
		except TypeError: self.m_table[var] = [self[var]] + val

	def prepend_value(self, var, value):
		if type(value) is types.ListType: val = value
		else: val = [value]
		#print var, self[var]
		try: self.m_table[var] = val + self[var]
		except TypeError: self.m_table[var] = val + [self[var]]

	# prepend unique would be ambiguous
	def append_unique(self, var, value):
		# first make certain we have a list
		v = self[var]
		if not type(v) is types.ListType: v = [v]

		# maybe we should use a set, but the order matters
		if type(value) is types.ListType:
			v += [x for x in value if not x in v]
		elif not value in v:
			v.append(value)
		self[var] = v

	def store(self, filename):
		"Write the variables into a file"
		file=open(filename, 'w')
		file.write('#VERSION=%s\n' % Params.g_version)
		keys=self.m_table.keys()
		keys.sort()
		for k in keys: file.write('%s = %r\n' % (k, self.m_table[k]))
		file.close()

	def load(self, filename):
		"Retrieve the variables from a file"
		if not os.path.isfile(filename): return 0
		file=open(filename, 'r')
		tbl = self.m_table
		for line in file:
			ln = line.strip()
			if not ln: continue
			if ln[:9]=='#VERSION=':
				if ln[9:] != Params.g_version: warning('waf upgrade? you should perhaps reconfigure')
			if ln[0]=='#': continue
			(key, value) = ln.split(' = ', 1)
			tbl[key] = eval(value)
		file.close()
		debug(self.m_table, 'env')
		return 1

	def get_destdir(self):
		"return the destdir, useful for installing"
		if self.m_table.has_key('NOINSTALL'): return ''
		dst = Params.g_options.destdir
		try: dst = os.path.join(dst, os.sep, self.m_table['SUBDEST'])
		except KeyError: pass
		return dst

	def set_dependency(self, infile, outfile):
		"TODO: future: set manual dependencies"
		pass

	def set_var_dependency(self, infile, text):
		"TODO: future: add manual dependencies on env variables"
		pass

