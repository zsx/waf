#! /usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2006 (ita)

"Python support"

import os, shutil
import Object, Action, Utils, Runner, Params

class pyobj(Object.genobj):
	s_default_ext = ['.py']
	def __init__(self):
		Object.genobj.__init__(self, 'other')
		self.pyopts = ''
		self.pyc = 1
		self.pyo = 0
		self.inst_var = 'PREFIX'
		self.inst_dir = 'lib'

	def apply(self):
		find_source_lst = self.path.find_source_lst

		envpyo = self.env.copy()
		envpyo['PYCMD']

		# first create the nodes corresponding to the sources
		for filename in self.to_list(self.source):
			node = find_source_lst(Utils.split_path(filename))

			base, ext = os.path.splitext(filename)
			#node = self.path.find_build(filename)
			if not ext in self.s_default_ext:
				fatal("unknown file "+filename)

			if self.pyc:
				task = self.create_task('pyc', self.env, 50)
				task.set_inputs(node)
				task.set_outputs(node.change_ext('.pyc'))
			if self.pyo:
				task = self.create_task('pyo', self.env, 50)
				task.set_inputs(node)
				task.set_outputs(node.change_ext('.pyo'))

	def install(self):
		for i in self.m_tasks:
			self.install_results('PREFIX', self.inst_dir, i)

def py_build(task, type):
	env = task.m_env
	infile = task.m_inputs[0].abspath(env)
	outfile = task.m_outputs[0].abspath(env)

	base = outfile[:outfile.rfind('.')]

	flag=''
	if type == '.pyo': flag='-O'

	code = "import sys, py_compile;py_compile.compile(sys.argv[1], sys.argv[2])"
	cmd = '%s %s -c "%s" %s %s' % (env['PYTHON'], flag, code, infile, outfile)

	if Params.g_verbose:
		print cmd

	ret = Runner.exec_command(cmd)
	return ret

def pyc_build(task):
	return py_build(task, '.pyc')

def pyo_build(task):
	return py_build(task, '.pyo')

def setup(env):
	Object.register('py', pyobj)
	Action.simple_action('pyc', '${PYTHON} -c ${PYCMD}', color='BLUE')
	Action.Action('pyc', vars=['PYTHON'], func=pyc_build)
	Action.Action('pyo', vars=['PYTHON'], func=pyo_build)

def detect(conf):
	python = conf.find_program('python', var='PYTHON')
	if not python: return 0

	return 1

