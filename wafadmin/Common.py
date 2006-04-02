#! /usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005 (ita)

# common builders and actions

import os, types, shutil
import Action, Object, Params, Runner, Scan
from Params import debug, error, trace, fatal

g_cppvalues = [
'FRAMEWORK', 'FRAMEWORKPATH',
'STATICLIB', 'LIB', 'LIBPATH', 'LINKFLAGS', 'RPATH',
'INCLUDE',
'CXXFLAGS', 'CCFLAGS', 'CPPPATH', 'CPPLAGS']

class InstallError:
	pass

def check_dir(dir):
	#print "check dir ", dir
	try:    os.stat(dir)
	except: os.makedirs(dir)

def install_files(var, subdir, files, env=None):
	if not Params.g_commands['install']: return

	if not env: env=Params.g_default_env
	node = Params.g_curdirnode

	if type(files) is types.ListType: lst=files
	else: lst = (' '+files).split()

	destpath = env[var]
	destdir = env['DESTDIR']
	if destdir: destpath = os.path.join(destdir, destpath.lstrip(os.sep))
	if subdir: destpath = os.path.join(destpath, subdir.lstrip(os.sep))

	check_dir(destpath)

	# copy the files to the final destination
	for filename in lst:
		file = os.path.join(node.abspath(), filename)
		print "* installing %s in %s" % (file, destpath)
		try: shutil.copy2( file, destpath )
		except: raise InstallError

def install_as(var, destfile, srcfile, env=None):
	if not Params.g_commands['install']: return

	if not env: env=Params.g_default_env
	node = Params.g_curdirnode

	try: tgt = os.path.join( env['DESTDIR'], env[var].lstrip(os.sep) )
	except: tgt = env[var]
	tgt = os.path.join(tgt, destfile.lstrip(os.sep))

	dir, name = os.path.split(tgt)
	check_dir(dir)

	src = os.path.join(node.abspath(), srcfile.lstrip(os.sep))
	print "* installing %s as %s" % (src, tgt)
	try: shutil.copy2( src, tgt )
	except: raise InstallError

# fake libtool files
fakelibtool_vardeps = ['CXX', 'PREFIX']
def fakelibtool_build(task):
	# Writes a .la file, used by libtool
	dest  = open(task.m_outputs[0].abspath(), 'w')
	sname = task.m_inputs[0].m_name
	dest.write("# Generated by ltmain.sh - GNU libtool 1.5.18 - (pwn3d by BKsys II code name WAF)\n#\n#\n")
	#if len(env['BKSYS_VNUM'])>0:
	#	vnum=env['BKSYS_VNUM']
	#	nums=vnum.split('.')
	#	src=source[0].name
	#	name = src.split('so.')[0] + 'so'
	#	strn = src+" "+name+"."+str(nums[0])+" "+name
	#	dest.write("dlname='%s'\n" % (name+'.'+str(nums[0])) )
	#	dest.write("library_names='%s'\n" % (strn) )
	#else:
	dest.write("dlname='%s'\n" % sname)
	dest.write("library_names='%s %s %s'\n" % (sname, sname, sname) )
	dest.write("old_library=''\ndependency_libs=''\ncurrent=0\n")
	dest.write("age=0\nrevision=0\ninstalled=yes\nshouldnotlink=no\n")
	dest.write("dlopen=''\ndlpreopen=''\n")
	dest.write("libdir='%s/lib'" % task.m_env['PREFIX'])
	dest.close()
	return 0
fakelibtoolact = Action.GenAction('fakelibtool', fakelibtool_vardeps, buildfunc=fakelibtool_build)

cpptypes=['shlib', 'program', 'staticlib']
cppvars=['CXXFLAGS','LINKFLAGS','obj_ext']
class cppobj(Object.genobj):
	def __init__(self, type='program'):
		Object.genobj.__init__(self, "other", "cpp")
		self.env = Params.g_default_env.copy()
		if not self.env.getValue('tools'):
			fatal('no tool selected')			
		self.m_type = type

		self.includes=''

		self.cxxflags=''
		self.cppflags=''
		self.ccflags=''

		self.linkflags=''
		self.linkpaths=''

		self.rpaths=''

		self.uselib=''
		self.useliblocal=''

		self._incpaths_lst=[]
		self._bld_incpaths_lst=[]

		global cpptypes
		if not type in cpptypes:
			error('Trying to build a cpp file of unknown type')

	def get_target_name(self, ext=None):
		prefix = self.env[self.m_type+'_PREFIX']
		suffix = self.env[self.m_type+'_SUFFIX']

		if ext: suffix = ext
		if not prefix: prefix=''
		if not suffix: suffix=''
		return ''.join([prefix, self.target, suffix])

	def apply(self):
		trace("apply called for cppobj")

		self.apply_lib_vars()
		self.apply_type_vars()
		self.apply_obj_vars()
		self.apply_incpaths()

		obj_ext = self.env['obj_ext'][0]

		# get the list of folders to use by the scanners
                # all our objects share the same include paths anyway
                tree = Params.g_build.m_tree
                dir_lst = { 'path_lst' : self._incpaths_lst }

		lst = self.source.split()
		cpptasks = []
		for filename in lst:

			node = self.m_current_path.find_node( filename.split(os.sep) )
			if not node:
				error("source not found "+filename)
				print self.m_current_path
				sys.exit(1)

			base, ext = os.path.splitext(filename)

			if tree.needs_rescan(node):
				tree.rescan(node, Scan.c_scanner, dir_lst)

			names = tree.get_raw_deps(node)

			# create the task for the cpp file
			cpptask = self.create_task('cpp', self.env)

			cpptask.m_scanner = Scan.c_scanner
			cpptask.m_scanner_params = dir_lst

			cpptask.m_inputs  = self.file_in(filename)
			cpptask.m_outputs = self.file_in(base+obj_ext)
			cpptasks.append(cpptask)

		# and after the cpp objects, the remaining is the link step
		# link in a lower priority (6) so it runs alone (default is 5)
		if self.m_type=='staticlib': linktask = self.create_task('arlink', self.env, 6)
		else:                        linktask = self.create_task('link', self.env, 6)
		cppoutputs = []
		for t in cpptasks: cppoutputs.append(t.m_outputs[0])
		linktask.m_inputs  = cppoutputs 
		linktask.m_outputs = self.file_in(self.get_target_name())

		self.m_linktask = linktask

		if self.m_type != 'program':	
			latask = self.create_task('fakelibtool', self.env, 7)
			latask.m_inputs = linktask.m_outputs
			latask.m_outputs = self.file_in(self.get_target_name('.la'))
			self.m_latask = latask

	def apply_incpaths(self):
		inc_lst = self.includes.split()
		lst = self._incpaths_lst

		# add the build directory
		self._incpaths_lst.append( Params.g_build.m_tree.m_bldnode )

		# now process the include paths
		tree = Params.g_build.m_tree
		for dir in inc_lst:
			node = self.m_current_path.find_node( dir.split(os.sep) )
			if not node:
				error("node not found dammit")
				continue
			lst.append( node )

			node2 = tree.get_mirror_node(node)
			lst.append( node2 )
			if Params.g_mode == 'nocopy':
				lst.append( node )
				self._bld_incpaths_lst.append(node)
			self._bld_incpaths_lst.append(node2)
			
		# now the nodes are added to self._incpaths_lst

	def apply_type_vars(self):
		trace('apply_type_vars called for cppobj')
		global cppvars
		for var in cppvars:
			# each compiler defines variables like 'shlib_CXXFLAGS', 'shlib_LINKFLAGS', etc
			# so when we make a cppobj of the type shlib, CXXFLAGS are modified accordingly
			compvar = '_'.join([self.m_type, var])
			#print compvar
			value = self.env[compvar]
			if value: self.env.appendValue(var, value)

	def apply_obj_vars(self):
		trace('apply_obj_vars called for cppobj')
		cpppath_st = self.env.getValue('CPPPATH_ST')
		lib_st = self.env.getValue('LIB_ST')
		staticlib_st = self.env.getValue('STATICLIB_ST')
		libpath_st = self.env.getValue('LIBPATH_ST')
		staticlibpath_st = self.env.getValue('STATICLIBPATH_ST')

		# local flags come first
		# set the user-defined includes paths
		if not self._incpaths_lst: self.apply_incpaths()
		for i in self._bld_incpaths_lst:
			self.env.appendValue('_CXXINCFLAGS', cpppath_st % i.bldpath())

		# set the library include paths
		for i in self.env.getValue('CPPPATH'):
			self.env.appendValue('_CXXINCFLAGS', cpppath_st % i)
			#print self.env['_CXXINCFLAGS']
			#print " appending include ",i
	
		# this is usually a good idea
		self.env.appendValue('_CXXINCFLAGS', cpppath_st % '.')
		try:
			tmpnode = Params.g_curdirnode
			tmpnode_mirror = Params.g_build.m_tree.self.m_src_to_bld[tmpnode]
			self.env.appendValue('_CXXINCFLAGS', cpppath_st % tmpnode.bldpath())
			self.env.appendValue('_CXXINCFLAGS', cpppath_st % tmpnode_mirror.bldpath())
		except:
			pass

		for i in self.env['LIB']:
			self.env.appendValue('LINKFLAGS', lib_st % i)

		for i in self.env['LIBPATH']:
			self.env.appendValue('LINKFLAGS', libpath_st % i)

		for i in self.env['STATICLIB']:
			self.env.appendValue('LINKFLAGS', staticlib_st % i)

		for i in self.env['LIBPATH']:
			self.env.appendValue('LINKFLAGS', staticlibpath_st % i)

	def apply_lib_vars(self):
		trace("apply_lib_vars called")

		libs = self.useliblocal.split()
		paths=[]
		for lib in libs:
			# TODO handle static libraries
			idx=len(lib)-1
			while 1:
				idx = idx - 1
				if lib[idx] == '/': break
			# find the path for linking and the library name
			path = lib[:idx]
			name = lib[idx+1:]
			if not path in paths: paths.append(path)
			self.env.appendValue('LIB', name)
		for p in paths:
			# now we need to transform the path into something usable
			node = self.m_current_path.find_node( [p] )
			self.env.appendValue('LIBPATH', node.srcpath())

		libs = self.uselib.split()
		global g_cppvalues
		for l in libs:
			for v in g_cppvalues:
				val=''
				try:    val = self.env[v+'_'+l]
				except: pass
				if val:
					self.env.appendValue(v, val)

# register our object
Object.register('cpp', cppobj)


## TODO rework the part below seriously
class ccobj(Object.genobj):
	def __init__(self):
		Object.genobj.__init__(self, "other", "cc")

	def apply(self):
		trace("apply called for ccobj")

		self.createTasks()

		for t in self.m_tasks:
			# sets nodes
			t.m_inputs  = self.file_in(self.source)
			t.m_outputs = self.file_in(self.target)
			t.debug()

# dummy action
def d_setcmd(task):
	task.m_cmd = "touch %s" % (task.m_outputs[0].bldpath())
def d_setsig(task):
	task.m_sig=Params.h_string( task.m_outputs[0].bldpath() )
def d_setstr(task):
	task.m_str=" -> dummy action is called : touch %s" % (task.m_outputs[0].bldpath())
Action.create_action('Dummy', d_setcmd, d_setsig, d_setstr)

class dummy(Object.genobj):
	def __init__(self):
		Object.genobj.__init__(self, "other", "Dummy")

	def apply(self):
		trace("apply called for dummy obj")

		self.createTasks()

		for t in self.m_tasks:
			# sets nodes
			t.m_inputs  = self.file_in(self.source)
			t.m_outputs = self.file_in(self.target)
			t.debug()


