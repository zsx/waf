#! /usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2006 (ita)

"""
Additional configuration checks hooked on the configuration class
we use the decorator notation: @conf
to attach the functions as methods on the Configure class (the conf object)
"""

import Utils, Configure, config_c
from Configure import conf
from Params import error, fatal

endian_str = '''
#include <stdio.h>
int is_big_endian()
{
	long one = 1;
	return !(*((char *)(&one)));
}
int main()
{
	if (is_big_endian()) printf("bigendian=1\\n");
	else printf("bigendian=0\\n");
	return 0;
}
'''

class compile_configurator(config_c.configurator_base):
	"inheritance demo"
	def __init__(self, conf):
		config_c.configurator_base.__init__(self, conf)
		self.name = ''
		self.code = ''
		self.flags = ''
		self.define = ''
		self.uselib = ''
		self.want_message = 0
		self.msg = ''
		self.force_compiler = None

	def error(self):
		fatal('test program would not run')

	def run_cache(self, retval):
		if self.want_message:
			self.conf.check_message('compile code (cached)', '', not (retval is False), option=self.msg)

	def validate(self):
		if not self.code:
			fatal('test configurator needs code to compile and run!')

	def run_test(self):
		obj = config_c.check_data()
		obj.code = self.code
		obj.env  = self.env
		obj.uselib = self.uselib
		obj.flags = self.flags
		if self.force_compiler: obj.force_compiler = self.force_compiler
		ret = self.conf.run_check(obj)

		if self.want_message:
			self.conf.check_message('compile code', '', not (ret is False), option=self.msg)

		return ret

@conf
def create_compile_configurator(self):
	return compile_configurator(self)

@conf
def checkEndian(self, define='', pathlst=[]):
	"""the point of checkEndian is to make an example, the following is better
	if sys.byteorder == "little":"""

	if define == '': define = 'IS_BIGENDIAN'

	if self.is_defined(define): return self.get_define(define)

	global endian

	test = self.create_test_configurator()
	test.code = endian_str
	code = test.run()['result']

	t = Utils.to_hashtable(code)
	try:
		is_big = int(t['bigendian'])
	except KeyError:
		raise Configure.ConfigurationError('endian test failed '+code)

	if is_big: strbig = 'big endian'
	else: strbig = 'little endian'
	self.check_message_custom('endianness', '', strbig)

	self.define_cond(define, is_big)
	return is_big

features_str = '''
#include <stdio.h>
int is_big_endian()
{
	long one = 1;
	return !(*((char *)(&one)));
}
int main()
{
	if (is_big_endian()) printf("bigendian=1\\n");
	else printf("bigendian=0\\n");
	printf("int_size=%d\\n", sizeof(int));
	printf("long_int_size=%d\\n", sizeof(long int));
	printf("long_long_int_size=%d\\n", sizeof(long long int));
	printf("double_size=%d\\n", sizeof(double));
	return 0;
}
'''

@conf
def checkFeatures(self, lst=[], pathlst=[]):

	global endian

	test = self.create_test_configurator()
	test.code = features_str
	code = test.run()['result']

	t = Utils.to_hashtable(code)
	try:
		is_big = int(t['bigendian'])
	except KeyError:
		raise Configure.ConfigurationError('endian test failed '+code)

	if is_big: strbig = 'big endian'
	else: strbig = 'little endian'
	self.check_message_custom('endianness', '', strbig)

	self.check_message_custom('int size', '', t['int_size'])
	self.check_message_custom('long int size', '', t['long_int_size'])
	self.check_message_custom('long long int size', '', t['long_long_int_size'])
	self.check_message_custom('double size', '', t['double_size'])

	self.define_cond('IS_BIGENDIAN', is_big)
	self.define_cond('INT_SIZE', int(t['int_size']))
	self.define_cond('LONG_INT_SIZE', int(t['long_int_size']))
	self.define_cond('LONG_LONG_INT_SIZE', int(t['long_long_int_size']))
	self.define_cond('DOUBLE_SIZE', int(t['double_size']))

	return is_big

@conf
def detect_platform(self):
	"""adapted from scons"""
	import os, sys
	if os.name == 'posix':
		if sys.platform == 'cygwin':
			return 'cygwin'
		if str.find(sys.platform, 'linux') != -1:
			return 'linux'
		if str.find(sys.platform, 'irix') != -1:
			return 'irix'
		if str.find(sys.platform, 'sunos') != -1:
			return 'sunos'
		if str.find(sys.platform, 'hp-ux') != -1:
			return 'hpux'
		if str.find(sys.platform, 'aix') != -1:
			return 'aix'
		if str.find(sys.platform, 'darwin') != -1:
			return 'darwin'
		return 'posix'
	elif os.name == 'os2':
		return 'os2'
	elif os.name == 'java':
		return 'java'
	else:
		return sys.platform

@conf
def find_header(self, header, define='', paths=''):
	if not define:
		define = 'HAVE_' + header.upper().replace('/', '_').replace('.', '_')
	test = self.create_header_enumerator()
	test.mandatory = 1
	test.name = header
	test.path = paths
	test.define = define
	return test.run()

@conf
def check_header(self, header, define='', mandatory=0):
	if not define:
		define = 'HAVE_' + header.upper().replace('/', '_').replace('.', '_')

	test = self.create_header_configurator()
	test.name = header
	test.define = define
	test.mandatory = mandatory
	return test.run()

@conf
def try_build_and_exec(self, code, uselib=''):
	test = self.create_test_configurator()
	test.uselib = uselib
	test.code = code
	ret = test.run()
	if ret: return ret['result']
	return None

@conf
def try_build(self, code, uselib='', msg='', force_compiler = ''):
	test = self.create_compile_configurator()
	test.uselib = uselib
	test.code = code
	if force_compiler:
		test.force_compiler = force_compiler
	if msg:
		test.want_message = 1
		test.msg = msg
	ret = test.run()
	return ret

@conf
def check_flags(self, flags, uselib='', options='', kind='cc', msg=1):
	test = self.create_test_configurator()
	test.uselib = uselib
	test.code = 'int main() {return 0;}\n'
	test.force_compiler = kind
	test.flags = flags
	ret = test.run()

	if msg: self.check_message('flags', flags, not (ret is False))

	if ret: return 1
	return None

# function wrappers for convenience
@conf
def check_header2(self, name, mandatory=1, define=''):
	import os
	ck_hdr = self.create_header_configurator()
	if define: ck_hdr.define = define
	# header provides no fallback for define:
	else: ck_hdr.define = 'HAVE_' + os.path.basename(name).replace('.','_').upper()
	ck_hdr.mandatory = mandatory
	ck_hdr.name = name
	return ck_hdr.run()

@conf
def check_library2(self, name, mandatory=1, uselib=''):
	ck_lib = self.create_library_configurator()
	if uselib: ck_lib.uselib = uselib
	ck_lib.mandatory = mandatory
	ck_lib.name = name
	return ck_lib.run()

@conf
def check_pkg2(self, name, version, mandatory=1, uselib=''):
	ck_pkg = self.create_pkgconfig_configurator()
	if uselib: ck_pkg.uselib = uselib
	ck_pkg.mandatory = mandatory
	ck_pkg.version = version
	ck_pkg.name = name
	return ck_pkg.run()

@conf
def check_cfg2(self, name, mandatory=1, define='', uselib=''):
	ck_cfg = self.create_cfgtool_configurator()
	if uselib: ck_cfg.uselib = uselib
	# cfgtool provides no fallback for uselib:
	else: ck_cfg.uselib = name.upper()
	ck_cfg.mandatory = mandatory
	ck_cfg.binary = name + '-config'
	return ck_cfg.run()

