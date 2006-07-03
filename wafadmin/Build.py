#! /usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005 (ita)

import os, os.path, sys, cPickle, types

import Environment, Params, Runner, Object, Utils, Node

from Params import debug, error, trace, fatal

def scan_src_path(i_parent_node, i_path, i_existing_nodes):

	# read the dir contents, ignore the folders in it
	l_names_read = os.listdir(i_path)

	# there are two ways to obtain the partitions:
	# 1 run the comparisons two times (not very smart)
	# 2 reduce the sizes of the list while looping

	l_names = l_names_read
	l_nodes = i_existing_nodes
	l_kept  = []

	for node in l_nodes:
		i     = 0
		name  = node.m_name
		l_len = len(l_names)
		while i < l_len:
			if l_names[i] == name:
				l_kept.append(node)
				break
			i += 1
		if i < l_len:
			l_names = l_names[:i-1]+l_names[i+1:]

	# Now:
	# l_names contains the new nodes (or files)
	# l_kept contains only nodes that actually exist on the filesystem
	for node in l_kept:
		try:
			# update the time stamp
			if not 0 in self.m_tstamp_variants: self.m_tstamp_variants[0] = {}
			self.m_tstamp_variants[0][node] = Params.h_file(node.abspath())
		except:
			fatal("a file is readonly or has become a dir "+node.abspath())

	l_path = i_path + os.sep
	for name in l_names:
		try:
			# will throw an exception if not a file or if not readable
			# we assume that this is better than performing a stat() first
			# TODO is it possible to distinguish the cases ?
			st = Params.h_file(l_path + name)
			l_child = Node.Node(name, i_parent_node)
			if not 0 in self.m_tstamp_variants: self.m_tstamp_variants[0] = {}
			self.m_tstamp_variants[0][node] = st
			l_kept.append(l_child)
		except:
			pass
	return l_kept


# in this function we do not add timestamps but we remove them
# when the files no longer exist (file removed in the build dir)
def scan_path(i_parent_node, i_path, i_existing_nodes, i_variant):

	# read the dir contents, ignore the folders in it
	l_names_read = os.listdir(i_path)

	# there are two ways to obtain the partitions:
	# 1 run the comparisons two times (not very smart)
	# 2 reduce the sizes of the list while looping

	l_names = l_names_read
	l_nodes = i_existing_nodes
	l_rm    = []
	#l_kept  = []

	for node in l_nodes:
		i     = 0
		name  = node.m_name
		l_len = len(l_names)
		while i < l_len:
			if l_names[i] == name:
				#l_kept.append(node)
				break
			i += 1
		if i < l_len:
			l_names = l_names[:i-1]+l_names[i+1:]
		else:
			l_rm.append(node)

	# remove the stamps of the nodes that no longer exist in the build dir
	for node in l_rm:
		# TODO remove this check in the future
		if not variant in self.m_tstamp_variants: self.m_tstamp_variants[variant] = {}
		self.m_tstamp_variants[variant].__delitem__(node)

class BuildDTO:
	def __init__(self, bdobj):
		pass
	def reset(self):
		self.m_root        = Node.Node('', None)
		self.m_blddir      = ''
		self.m_srcnode     = None
		self.m_src_to_bld  = {}
		self.m_bld_to_src  = {}
		self.m_depends_on  = {}
		self.m_deps_tstamp = {}
		self.m_raw_deps    = {}
		self.m_sigs        = {}
		self.m_tstamp_variants = {}
	def init(self, bdobj):
		self.m_root        = bdobj.m_root
		self.m_blddir      = bdobj.m_blddir
		self.m_srcnode     = bdobj.m_srcnode
		self.m_src_to_bld  = bdobj.m_src_to_bld
		self.m_bld_to_src  = bdobj.m_bld_to_src
		self.m_depends_on  = bdobj.m_depends_on
		self.m_deps_tstamp = bdobj.m_deps_tstamp
		self.m_raw_deps    = bdobj.m_raw_deps
		self.m_sigs        = bdobj.m_sigs
		self.m_tstamp_variants = bdobj.m_tstamp_variants
	def update_build(self, bdobj):
		bdobj.m_root        = self.m_root
		bdobj.m_blddir      = self.m_blddir
		bdobj.m_srcnode     = self.m_srcnode
		bdobj.m_src_to_bld  = self.m_src_to_bld
		bdobj.m_bld_to_src  = self.m_bld_to_src
		bdobj.m_depends_on  = self.m_depends_on
		bdobj.m_deps_tstamp = self.m_deps_tstamp
		bdobj.m_raw_deps    = self.m_raw_deps
		bdobj.m_sigs        = self.m_sigs
		bdobj.m_tstamp_variants = self.m_tstamp_variants

class Build:
	def __init__(self):

		# ======================================= #
		# dependency tree

		# filesystem root - root name is Params.g_rootname
		self.m_root = Node.Node('', None)

		self.m_name2nodes  = {}             # access nodes quickly
		self.m_blddir      = ''
		self.m_srcnode     = None           # source directory

		# nodes signatures: self.m_tstamp_variants[variant_name][node] = signature_value
		self.m_tstamp_variants = {}

		# one node has nodes it depends on, tasks cannot be stored
		# node -> [node; node; node ..] - all dependencies
		# m_depends_on[node] = [node1, node2, ..]
		self.m_depends_on  = {}

		# m_deps_tstamp[node] = represents the timestamp for the node last scan
		self.m_deps_tstamp = {}

		# results of a scan: self.m_raw_deps[node] = [filename1, filename2, filename3]
		# for example, find headers in c files
		self.m_raw_deps    = {}


		# signatures for nodes that are created in the builddir
		self.m_sigs        = {}

		# give flags to nodes (eg: existing->1, not existing->0)
		self._flags        = {}

		# ======================================= #
		# globals

		# map a name to an environment, the 'default' must be defined
		self.m_allenvs = {}

		# build dir variants (release, debug, ..)
		self.m_variants = ['default']

		# there should be only one build dir in use at a time
		Params.g_build = self

		# ======================================= #
		# code for reading the scripts

		# project build directory
		self.m_bdir = ''

		# the current directory from which the code is run
		# the folder changes everytime a wscript is read
		self.m_curdirnode = None

		# temporary holding the subdirectories containing scripts
		self.m_subdirs=[]

		# ======================================= #
		# cache variables

		# local cache for absolute paths
		self.m_abspath_cache = {}

		# local cache for relative paths
		# two nodes - hashtable of hashtables - g_relpath_cache[child][parent])
		self._relpath_cache = {}

		# cache for height of the node (amount of folders from the root)
		self._height_cache = {}

		# list of folders that are already scanned
		# so that we do not need to stat them one more time
		self._scanned_folders  = []

		# file contents
		self._cache_node_content = {}

		# ======================================= #
		# tasks and objects

		# objects that are not posted and objects already posted
		# -> delay task creation
		self.m_outstanding_objs = []
		self.m_posted_objs      = []


		# TODO obsolete
		# get bld nodes from src nodes quickly
		self.m_src_to_bld  = {}
		# get src nodes from bld nodes quickly
		self.m_bld_to_src  = {}

		# TODO obsolete
		#self.m_dirs     = []   # folders in the dependency tree to scan
		#self.m_rootdir  = ''   # root of the build, in case if the build is moved ?

	# load existing data structures from the disk (stored using self._store())
	def _load(self):
		try:
			file = open(os.path.join(self.m_bdir, Params.g_dbfile), 'rb')
			dto = cPickle.load(file)
			dto.update_build(self)
			file.close()
		except:
			debug("resetting the build object (previous attempt failed)")
			dto = BuildDTO(self)
			dto.reset()
			dto.update_build(self)
			
		# reset the flags of the tree
		self.m_root.tag(0)

	# store the data structures on disk, retrieve with self._load()
	def _store(self):
		file = open(os.path.join(self.m_bdir, Params.g_dbfile), 'wb')
		cPickle.dump(BuildDTO(self), file, -1)
		file.close()

	# ======================================= #

	def save(self):
		self._cleanup()
		self._store()

	# TODO: is this really useful ?
	# usual computation types - dist and distclean might come here too
	def clean(self):
		trace("clean called")

	# keep
	def compile(self):
		trace("compile called")

		os.chdir(self.m_bdir)

		Object.flush()
		if Params.g_maxjobs <=1:
			generator = Runner.JobGenerator(self)
			executor = Runner.Serial(generator)
		else:
			executor = Runner.Parallel(self, Params.g_maxjobs)

		trace("executor starting")
		try:
			ret = executor.start()
		except KeyboardInterrupt:
			os.chdir(self.m_srcnode.abspath())
			self._store()
			raise
		#finally:
		#	os.chdir( self.m_srcnode.abspath() )

		os.chdir( self.m_srcnode.abspath() )
		return ret

	# this function is called for both install and uninstall
	def install(self):
		trace("install called")
		Object.flush()
		for obj in Object.g_allobjs: obj.install()

	# keep
	def add_subdirs(self, dirs):
		import Scripting
		if type(dirs) is types.ListType: lst = dirs
		else: lst = dirs.split()

		for d in lst:
			if not d: continue
			Scripting.add_subdir(d, self)

	# keep
	def create_obj(self, objname, *k, **kw):
		try:
			return Object.g_allclasses[objname](*k, **kw)
		except:
			print "error in create_obj", objname
			raise

	# ======================================= #
	# node and folder handling

	# this should be the main entry point
	def load_dirs(self, srcdir, blddir):
		# this functions should be the start
		# there is no reason to bypass this check
		try:
			if srcdir == blddir or os.path.samefile(srcdir, blddir):
				fatal("build dir must be different from srcdir ->"+str(srcdir)+" ->"+str(blddir))
		except:
			pass

		# set the source directory
		srcdir = os.path.abspath('.') + os.sep + srcdir

		self.m_srcnode = self.ensure_node_from_path(srcdir)
		debug("srcnode is "+str(self.m_srcnode)+" and srcdir "+srcdir)

		self.m_curdirnode = self.m_srcnode

		# set the build directory it is a path, not a node (either absolute or relative)
		if blddir[0] != '/':
			self.m_bdir = os.path.abspath(blddir)
		else:
			self.m_bdir = blddir
		print "self.m_bdir is ", self.m_bdir

		self.m_bldnode = self.ensure_node_from_path(self.m_bdir)

		# create this build dir if necessary
		try: os.makedirs(blddir)
		except: pass

		#self._load()
		#self._set_blddir(blddir)
		#self._duplicate_srcdir(srcdir, scan)

		# TODO

	# return a node corresponding to an absolute path, creates nodes if necessary
	def ensure_node_from_path(self, abspath):
		trace('ensure_node_from_path %s' % (abspath))
		plst = abspath.split('/')
		curnode = self.m_root # root of the tree
		for dirname in plst:
			if not dirname: continue
			found=None
			for cand in curnode.m_dirs:
				if cand.m_name == dirname:
					found = cand
					break
			if not found:
				found = Node.Node(dirname, curnode)
				curnode.m_dirs.append(found)
			curnode = found
		return curnode

	# ======================================= #
	def rescan(self, src_dir_node):
		# first list the files in the src dir and update the nodes
		# for each variant build dir (multiple build dirs):
		#     list the files in the build dir, update the nodes
		#
		# this makes (n bdirs)+srdir to scan (at least 2 folders)
		# so we might want to do it in parallel in the future

		debug("rescanning "+str(src_dir_node))

		# list the files in the src directory, adding the signatures
		files = scan_src_path(src_dir_node, src_dir_node.abspath(), src_dir_node.m_files)
		src_dir_node.m_files = files

		# list the files in the build dirs
		# remove the existing timestamps if the build files are removed
		lst = self.m_srcnode.difflst(src_dir_node)
		for variant in self.m_variants:
			if not variant in self.m_tstamp_variants: self.m_tstamp_variants[variant] = {}
			sub_path = os.sep.join([self.m_bldnode.abspath(), variant] + lst)
			try:
				files = scan_path(src_dir_node, sub_path, src_dir_node.m_build, variant)
				src_dir_node.m_build = files
			except:
				# listdir failed, remove all sigs of nodes
				dict = self.m_tstamp_variants[variant]
				for node in src_dir_node.m_build:
					dict.__delitem__(node)
				os.makedirs(sub_path)
				src_dir_node.m_build = []

	def ensure_directory_lst(self, node, plst):
		curnode = node
		exists  = 1
		for dirname in plst:
			#print "finding ", dirname
			if not dirname: continue

			# try to find the node in existing deptree
			found=None
			for cand in curnode.m_dirs:
				if cand.m_name == dirname:
					found = cand
					break
			# the node is found and is already scanned, keep walking
			try:
				if found and self.m_flags[found]>0:
					curnode=found
					continue
			except: pass

			# the node is not found, add it
			if not found:
				found = Node.Node(dirname, curnode)
				curnode.m_dirs.append(found)
			# we have a node, but it is not scanned
			curnode = found
			try: os.stat(curnode.abspath())
			except OSError:
				exists = 0
				trace("make dir %s"%curnode.abspath())
				try: os.mkdir(curnode.abspath())
				except: trace('mkdir failed '+curnode.abspath())
				#st=os.stat(curnode.abspath())
				# TRICK_1: the subtree is obsolete -> forget sub-nodes recursively
				curnode.m_dirs=[]
				curnode.m_files=[]
			self.m_flags[curnode] = 1
		return (exists, curnode)



	# tell if a node has changed, to update the cache
	def needs_rescan(self, node):
		#print "needs_rescan for ", node, node.m_tstamp
		try:
			if self.m_deps_tstamp[node] == node.m_tstamp:
				#print "no need to rescan", node.m_tstamp
				return 0
		except:
			pass
		return 1

	# Fast node access - feed an internal dictionary (to keep between runs -> TODO not sure)
	def store_node(self, node):
		nn=node.m_name
		try:
			# prevent silly errors
			if node in self.m_name2nodes[nn]: print "BUG: name2nodes already contains node!", nn
			else: self.m_name2nodes[nn].append(node)
		except:
			self.m_name2nodes[nn] = [node]


	## IMPORTANT - for debugging
	def dump(self):
		def printspaces(count):
			if count>0: return printspaces(count-1)+"-"
			return ""
		def recu(node, count):
			accu = printspaces(count)
			accu+= "> "+node.m_name+" (d)\n"
			for child in node.m_files:
				accu+= printspaces(count)
				accu+= '> '+child.m_name+' '
				accu+= ' '+str(child.m_tstamp)+'\n'
				# TODO #if node.m_files[file].m_newstamp != node.m_files[file].m_oldstamp: accu += "\t\t\t(modified)"
				#accu+= node.m_files[file].m_newstamp + "< >" + node.m_files[file].m_oldstamp + "\n"
			for dir in node.m_dirs: accu += recu(dir, count+1)
			return accu

		Params.pprint('CYAN', recu(self.m_root, 0) )
		Params.pprint('CYAN', 'size is '+str(self.m_root.size()))

		#keys = self.m_name2nodes.keys()
		#for k in keys:
		#	print k, '\t\t', self.m_name2nodes[k]




	# ======================================= #
	# obsolete code

	# TODO OBSOLETE
	def _duplicate_srcdir(self, dir, scan='auto'):
		trace("duplicate_srcdir")
		srcnode = self.m_srcnode

		# stupid behaviour (will scan every project in the folder) but scandirs-free
		# we will see later for more intelligent behaviours (scan only folders that contain sources..)
		try:
			Params.g_excludes=Params.g_excludes+Utils.g_module.prunedirs
		except:
			pass

		if scan == 'auto':
			trace("autoscan in use")
			# This function actually dupes the dirs with 'scanner_mirror'
			def scan(node):
				if node is Params.g_build.m_bldnode: return []
				if node.m_name in Params.g_excludes: return []
				dir = os.sep.join(srcnode.difflst(node))
				self.scanner_mirror(dir)
				return node.m_dirs
			mlst = scan(srcnode)
			while mlst:
				el=mlst[0]
				mlst=mlst[1:]
				mlst += scan(el)
		else:
			dirs = []
			for tgt in self.m_subdirs:
				dirs.append( os.sep.join(srcnode.difflst(tgt[0]) ) )
			self.scandirs( dirs )
			

