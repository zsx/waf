#!/usr/bin/env python
# encoding: utf-8
# Thomas Nagy, 2005 (ita)

import re, logging, traceback, sys
import Utils
from Constants import *

zones = ''
verbose = 0

re_log = re.compile(r'(\w+): (.*)', re.M)
class log_filter(logging.Filter):
	def __init__(self, name=None):
		pass

	def filter(self, rec):
		col = Utils.colors
		rec.c1 = col.get('PINK', '')
		rec.c2 = col.get('NORMAL','')
		rec.zone = rec.module
		if rec.levelno >= logging.INFO:
			if rec.levelno >= logging.ERROR:
				rec.c1 = col.get('RED', '')
			return True

		zone = ''
		m = re_log.match(rec.msg)
		if m:
			zone = rec.zone = m.group(1)
			rec.msg = m.group(2)

		if zones:
			return getattr(rec, 'zone', '') in zones or '*' in zones
		elif not verbose > 2:
			return False
		return True

class formatter(logging.Formatter):
	def __init__(self):
		logging.Formatter.__init__(self, LOG_FORMAT, HOUR_FORMAT)

	def format(self, rec):
		if rec.levelno >= logging.WARNING:
			return '%s%s%s' % (rec.c1, rec.msg, rec.c2)
		return logging.Formatter.format(self, rec)

def fatal(msg, ret=1):
	if verbose:
		st = traceback.extract_stack()
		if st: st = st[:-1]
		buf = []
		for filename, lineno, name, line in st:
			buf.append('  File "%s", line %d, in %s' % (filename, lineno, name))
			if line:
				buf.append('    %s' % line.strip())
		msg = msg + "\n".join(buf)
	logging.critical(msg)
	sys.exit(ret)
#logging.fatal = fatal
debug = logging.debug
warn = logging.warn
error = logging.error

def init_log():
	log = logging.getLogger()
	log.handlers = []
	hdlr = logging.StreamHandler()
	hdlr.setFormatter(formatter())
	log.addHandler(hdlr)
	log.addFilter(log_filter())
	log.setLevel(logging.DEBUG)

