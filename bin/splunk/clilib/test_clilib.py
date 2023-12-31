from __future__ import absolute_import
import logging as logger
import os
import splunk.clilib.cli_common as comm
from splunk.clilib import control_exceptions as cex
from splunk.util import pytest_mark_skip_conditional

PYTHON_CMD = "python"

ARG_FILE   = "file"

def makeScriptCmd(script):
  # 2nd arg is quoted in case $SPLUNK_HOME has spaces in it.
  return "%s \"%s\"" % (PYTHON_CMD, os.path.join(comm.SPLUNK_PY_PATH, "mining", script))

@pytest_mark_skip_conditional(reason="SPL-175665: Probably a regression or functional test now")
def testDates(args, fromCLI):
  args = comm.getAnonArgs(args)
  if 0 == len(args):
    raise cex.ArgError("At least one argument is required.  Usage:\n"
        + "splunk test dates \"<string>\" OR\n"
        + "splunk test dates file <filename>")

  # build a string that will end up like: parsetest "foo" "bar baz".  quotes are fun.
  argString = str.join(str(" "), [("\"%s\"" % x) for x in args])
  os.system("parsetest " + argString)

@pytest_mark_skip_conditional(reason="SPL-175665: Probably a regression or functional test now")
def testFields(args, fromCLI):
  paramsReq = ()
  paramsOpt = ()
  comm.validateArgs(paramsReq, paramsOpt, args)
  os.system(makeScriptCmd("interactiveLearner.py"))

@pytest_mark_skip_conditional(reason="SPL-175665: Probably a regression or functional test now")
def testSourcetypes(args, fromCLI):
  paramsReq = (ARG_FILE,)
  paramsOpt = ()
  comm.validateArgs(paramsReq, paramsOpt, args)
  os.system("classify \"%s\"" % args[ARG_FILE])
