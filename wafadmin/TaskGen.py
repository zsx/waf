#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005-2008 (ita)

"""
The class task_gen encapsulates the creation of task objects (low-level code)
The instances can have various parameters, but the creation of task nodes (Task.py)
is delayed. To achieve this, various methods are called from the method "apply"

The class task_gen contains lots of methods, and a configuration table:
* the methods to call (self.meths) can be specified dynamically (removing, adding, ..)
* the order of the methods (self.prec or by default task_gen.prec) is configurable
* new methods can be inserted dynamically without pasting old code

Additionally, task_gen provides the method "process_source"
* file extensions are mapped to methods: def meth(self, name_or_node)
* if a mapping is not found in self.mappings, it is searched in task_gen.mappings
* when called, the functions may modify self.allnodes to re-add source to process
* the mappings can map an extension or a filename (see the code below)

WARNING: subclasses must reimplement the clone method
"""

import os, traceback, copy
import Build, Task, Utils, Logs, Options
from collections import defaultdict
from Logs import debug, error, warn
from Constants import *
from Base import WafError, WscriptError

class task_gen(object):
	"""
	Most methods are of the form 'def meth(self):' without any parameters
	there are many of them, and they do many different things:
	* task creation
	* task results installation
	* environment modification
	* attribute addition/removal

	The inheritance approach is complicated
	* mixing several languages at once
	* subclassing is needed even for small changes
	* inserting new methods is complicated

	This new class uses a configuration table:
	* adding new methods easily
	* obtaining the order in which to call the methods
	* postponing the method calls (post() -> apply)

	Additionally, a 'traits' static attribute is provided:
	* this list contains methods
	* the methods can remove or add methods from self.meths
	Example1: the attribute 'staticlib' is set on an instance
	a method set in the list of traits is executed when the
	instance is posted, it finds that flag and adds another method for execution
	Example2: a method set in the list of traits finds the msvc
	compiler (from self.env['MSVC']==1); more methods are added to self.meths
	"""

	mappings = {}
	prec = defaultdict(list)
	traits = defaultdict(set)
	classes = {}

	def __init__(self, *kw, **kwargs):
		self.prec = defaultdict(list)
		"map precedence of function names to call"
		# so we will have to play with directed acyclic graphs
		# detect cycles, etc

		self.source = ''
		self.target = ''

		# list of methods to execute - does not touch it by hand unless you know
		self.meths = []

		# list of mappings extension -> function
		self.mappings = {}

		# list of features (see the documentation on traits)
		self.features = list(kw)

		# not always a good idea
		self.tasks = []

		self.default_chmod = O644
		self.default_install_path = None

		# kind of private, beware of what you put in it, also, the contents are consumed
		self.allnodes = []

		self.bld = kwargs['bld']
		self.env = self.bld.env.derive()

		self.path = self.bld.path # emulate chdir when reading scripts
		self.name = '' # give a name to the target (static+shlib with the same targetname ambiguity)

		# provide a unique id
		self.idx = self.bld.idx[id(self.path)] = self.bld.idx.get(id(self.path), 0) + 1

		for key, val in kwargs.items():
			setattr(self, key, val)

		self.bld.task_manager.add_task_gen(self)
		self.bld.all_task_gen.append(self)

	def __str__(self):
		return ("<task_gen '%s' declared in %s>" % (self.name or self.target, self.path))

	def to_list(self, value):
		"helper: returns a list"
		if isinstance(value, str): return value.split()
		else: return value

	def apply(self):
		"order the methods to execute using self.prec or task_gen.prec"
		keys = set(self.meths)

		# add the methods listed in the features
		self.features = Utils.to_list(self.features)
		for x in self.features + ['*']:
			st = task_gen.traits[x]
			if not st:
				warn('feature %r does not exist - bind at least one method to it' % x)
			keys.update(st)

		# copy the precedence table
		prec = {}
		prec_tbl = self.prec or task_gen.prec
		for x in prec_tbl:
			if x in keys:
				prec[x] = prec_tbl[x]

		# elements disconnected
		tmp = []
		for a in keys:
			for x in prec.values():
				if a in x: break
			else:
				tmp.append(a)

		# topological sort
		out = []
		while tmp:
			e = tmp.pop()
			if e in keys: out.append(e)
			try:
				nlst = prec[e]
			except KeyError:
				pass
			else:
				del prec[e]
				for x in nlst:
					for y in prec:
						if x in prec[y]:
							break
					else:
						tmp.append(x)

		if prec: raise WafError("graph has a cycle %s" % str(prec))
		out.reverse()
		self.meths = out

		# then we run the methods in order
		debug('task_gen: posting %s %d' % (self, id(self)))
		for x in out:
			try:
				v = getattr(self, x)
			except AttributeError:
				raise WafError("tried to retrieve %s which is not a valid method" % x)
			debug('task_gen: -> %s (%d)' % (x, id(self)))
			v()

	def post(self):
		"runs the code to create the tasks, do not subclass"
		if not self.name:
			if isinstance(self.target, list):
				self.name = ' '.join(self.target)
			else:
				self.name = self.target

		if getattr(self, 'posted', None):
			#error("OBJECT ALREADY POSTED" + str( self))
			return
		self.apply()
		debug('task_gen: posted %s' % self.name)
		self.posted = True

	def get_hook(self, ext):
		try: return self.mappings[ext]
		except KeyError:
			try: return task_gen.mappings[ext]
			except KeyError: return None

	# TODO waf 1.6: always set the environment
	# TODO waf 1.6: create_task(self, name, inputs, outputs)
	def create_task(self, name, src=None, tgt=None, env=None):
		env = env or self.env
		task = Task.TaskBase.classes[name](env=env.derive(), generator=self)
		if src:
			task.set_inputs(src)
		if tgt:
			task.set_outputs(tgt)
		self.tasks.append(task)
		return task

	def name_to_obj(self, name):
		return self.bld.name_to_obj(name, self.env)

	def clone(self, env):
		""
		newobj = task_gen(bld=self.bld)
		for x in self.__dict__:
			if x in ['env', 'bld']:
				continue
			elif x in ["path", "features"]:
				setattr(newobj, x, getattr(self, x))
			else:
				setattr(newobj, x, copy.copy(getattr(self, x)))

		newobj.__class__ = self.__class__
		if isinstance(env, str):
			newobj.env = self.bld.all_envs[env].derive()
		else:
			newobj.env = env.derive()

		return newobj

	def get_inst_path(self):
		return getattr(self, '_install_path', getattr(self, 'default_install_path', ''))

	def set_inst_path(self, val):
		self._install_path = val

	install_path = property(get_inst_path, set_inst_path)

	def get_chmod(self):
		return getattr(self, '_chmod', getattr(self, 'default_chmod', O644))

	def set_chmod(self, val):
		self._chmod = val

	chmod = property(get_chmod, set_chmod)

def declare_chain(name='', rule=None, reentrant=True, color='BLUE',
	ext_in=[], ext_out=[], before=[], after=[], decider=None, install=False, scan=None):
	"""
	see Tools/flex.py for an example
	while i do not like such wrappers, some people really do
	"""

	if isinstance(rule, str):
		act = Task.simple_task_type(name, rule, color=color)
	else:
		act = Task.task_type_from_func(name, rule, color=color)

	act.ext_in = Utils.to_list(ext_in)
	act.ext_out = Utils.to_list(ext_out)
	act.before = Utils.to_list(before)
	act.after = Utils.to_list(after)
	act.scan = scan

	def x_file(self, node):
		if decider:
			ext = decider(self, node)
		elif isinstance(act.ext_out, str):
			ext = act.ext_out

		out_source = [node.change_ext(x) for x in ext]
		if reentrant:
			for i in range(reentrant):
				self.allnodes.append(out_source[i])
		tsk = self.create_task(name, node, out_source)

		if node.__class__.bld.is_install:
			tsk.install = install

	for x in Utils.to_list(var):
		task_gen.mappings[act.ext_in] = x_file

def taskgen_method(func):
	"""
	register a method as a task generator method
	"""
	setattr(task_gen, func.__name__, func)
	return func

def feature(*k):
	"""
	declare a task generator method that will be executed when the
	object attribute 'feature' contains the corresponding key(s)
	"""
	def deco(func):
		setattr(task_gen, func.__name__, func)
		for name in k:
			task_gen.traits[name].update([func.__name__])
		return func
	return deco

def before(*k):
	"""
	declare a task generator method which will be executed
	before the functions of given name(s)
	"""
	def deco(func):
		setattr(task_gen, func.__name__, func)
		for fun_name in k:
			if not func.__name__ in task_gen.prec[fun_name]:
				task_gen.prec[fun_name].append(func.__name__)
		return func
	return deco

def after(*k):
	"""
	declare a task generator method which will be executed
	after the functions of given name(s)
	"""
	def deco(func):
		setattr(task_gen, func.__name__, func)
		for fun_name in k:
			if not fun_name in task_gen.prec[func.__name__]:
				task_gen.prec[func.__name__].append(fun_name)
		return func
	return deco

def extension(*k):
	"""
	declare a task generator method which will be invoked during
	the processing of source files for the extension given
	"""
	def deco(func):
		setattr(task_gen, func.__name__, func)
		for x in k:
			task_gen.mappings[x] = func
		return func
	return deco

# ##############################################################
# The following methods are task generator methods commonly used

def process_source(self):
	"""
	Process each element in the attribute 'source', assuming it represents
	a list of source (nodes or file names)
	process the files by extension"""

	find = self.path.find_resource
	for el in self.to_list(self.source):
		if isinstance(el, str):
			node = find(el)
			if not node:
				raise WafError("source not found: '%s' in '%s'" % (el, self.path))
		else:
			node = el
		self.allnodes.append(node)

	for node in self.allnodes:
		# self.mappings or task_gen.mappings map the file extension to a function
		x = self.get_hook(node.suffix())
		if not x:
			raise WafError("File %r has no mapping in %r (did you forget to load a waf tool?)" % (node, self.__class__.mappings.keys()))
		x(self, node)
feature('*')(process_source)

def process_rule(self):
	"""
	Process the attribute rule, when provided the method process_source will be disabled
	"""
	if not getattr(self, 'rule', None):
		return

	try:
		self.meths.remove('process_source')
	except ValueError:
		# already removed?
		pass

	# get the function and the variables
	func = self.rule
	vars2 = []
	if isinstance(func, str):
		# use the shell by default for user-defined commands
		(func, vars2) = Task.compile_fun('', self.rule, shell=getattr(self, 'shell', True))
		func.code = self.rule

	vars = getattr(self, 'vars', vars2)
	if not vars:
		if isinstance(self.rule, str):
			vars = self.rule
		else:
			vars = Utils.h_fun(self.rule)

	# create the task class
	name = getattr(self, 'name', None) or self.target or self.rule
	cls = Task.task_type_from_func(name, func, vars)

	# now create one instance
	tsk = self.create_task(name)

	# we assume that the user knows that without inputs or outputs
	#if not getattr(self, 'target', None) and not getattr(self, 'source', None):
	#	cls.quiet = True

	if getattr(self, 'target', None):
		cls.quiet = True
		tsk.outputs = [self.path.find_or_declare(x) for x in self.to_list(self.target)]

	if getattr(self, 'source', None):
		cls.quiet = True
		tsk.inputs = []
		for x in self.to_list(self.source):
			y = self.path.find_resource(x)
			if not y:
				raise WafError('input file %r could not be found (%r)' % (x, self.path.abspath()))
			tsk.inputs.append(y)

	if getattr(self, 'always', None):
		Task.always_run(cls)

	if getattr(self, 'scan', None):
		cls.scan = self.scan

	if getattr(self, 'install_path', None):
		tsk.install_path = self.install_path

	if getattr(self, 'cwd', None):
		tsk.cwd = self.cwd

	if getattr(self, 'on_results', None):
		Task.update_outputs(cls)

	for x in ['after', 'before', 'ext_in', 'ext_out']:
		setattr(cls, x, getattr(self, x, []))

feature('*')(process_rule)
before('process_source')(process_rule)

def sequence_order(self):
	"""
	Add a strict sequential constraint between the tasks generated by task generators
	It works because task generators are posted in order
	it will not post objects which belong to other folders

	This is more an example than a widely-used solution

	Note that the method is executed in last position

	to use:
	bld.new_task_gen(features='javac seq')
	bld.new_task_gen(features='jar seq')

	to start a new sequence, set the attribute seq_start, for example:
	obj.seq_start = True
	"""
	if self.meths and self.meths[-1] != 'sequence_order':
		self.meths.append('sequence_order')
		return

	if getattr(self, 'seq_start', None):
		return

	# all the tasks previously declared must be run before these
	if getattr(self.bld, 'prev', None):
		self.bld.prev.post()
		for x in self.bld.prev.tasks:
			for y in self.tasks:
				y.set_run_after(x)

	self.bld.prev = self
feature('seq')(sequence_order)

