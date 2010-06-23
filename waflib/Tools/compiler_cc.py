#!/usr/bin/env python
# encoding: utf-8
# Matthias Jahn jahn dôt matthias ât freenet dôt de, 2007 (pmarat)

import os, sys, imp, types
from waflib.Tools import ccroot
from waflib import Utils, Configure, Options
from waflib.Logs import debug

def build(bld):
	print test

c_compiler = {
'win32':  ['msvc', 'gcc'],
'cygwin': ['gcc'],
'darwin': ['gcc'],
'aix':    ['xlc', 'gcc'],
'linux':  ['gcc', 'icc', 'suncc'],
'sunos':  ['gcc', 'suncc'],
'irix':   ['gcc'],
'hpux':   ['gcc'],
'gnu':    ['gcc'],
'default': ['gcc']
}

def __list_possible_compiler(platform):
	try:
		return c_compiler[platform]
	except KeyError:
		return c_compiler["default"]

def configure(conf):
	"""
	for each compiler for the platform, try to configure the compiler
	in theory the tools should raise a configuration error if the compiler
	pretends to be something it is not (setting CC=icc and trying to configure gcc)
	"""
	try: test_for_compiler = Options.options.check_c_compiler
	except AttributeError: conf.fatal("Add options(opt): opt.tool_options('compiler_cc')")
	orig = conf.env
	for compiler in test_for_compiler.split():
		try:
			conf.start_msg('Checking for %r (c compiler)' % compiler)
			conf.env = orig.derive()
			conf.check_tool(compiler)
		except conf.errors.ConfigurationError as e:
			conf.end_msg(False)
			debug('compiler_cc: %r' % e)
		else:
			if conf.env['CC']:
				orig.table = conf.env.get_merged_dict()
				conf.env = orig
				conf.end_msg(True)
				conf.env['COMPILER_CC'] = compiler
				break
			conf.end_msg(False)
	else:
		conf.fatal('could not configure a c compiler!')

def options(opt):
	build_platform = Utils.unversioned_sys_platform()
	possible_compiler_list = __list_possible_compiler(build_platform)
	test_for_compiler = ' '.join(possible_compiler_list)
	cc_compiler_opts = opt.add_option_group("C Compiler Options")
	cc_compiler_opts.add_option('--check-c-compiler', default="%s" % test_for_compiler,
		help='On this platform (%s) the following C-Compiler will be checked by default: "%s"' % (build_platform, test_for_compiler),
		dest="check_c_compiler")

	for c_compiler in test_for_compiler.split():
		opt.tool_options('%s' % c_compiler, option_group=cc_compiler_opts)

