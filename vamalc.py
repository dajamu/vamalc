#!/usr/bin/env python

import dns.resolver
import logging
import os
import pycurl
import re
import shlex
import shutil
import subprocess
import sys

DBDIR    = "/var/tmp/clam"
MIRROR   = "http://database.clamav.net"
PROGRESS = 0

def fetch(url, fname):
	global PROGRESS
	logging.info("Fetching '%s' to file '%s'..." % (url, fname))

	with open(fname, 'wb') as f:
		c = pycurl.Curl()

		c.setopt(pycurl.NOPROGRESS, False)
		c.setopt(pycurl.URL, url)
		c.setopt(pycurl.USERAGENT, "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36")
		c.setopt(pycurl.WRITEDATA, f)
		c.setopt(pycurl.PROGRESSFUNCTION, fetchCallback)

		c.perform()
		c.close()

	PROGRESS = 0

def fetchCallback(dtot, dcur, utot, ucur):
	if dtot > 0:
		global PROGRESS

		pc = int(100 * dcur / dtot)

		if pc % 5 == 0:
			if pc > PROGRESS:
				PROGRESS = pc
				logging.debug("%d%%" % pc)

def getLocalVersion(fname):
	cmd = "/opt/clamav/current/bin/sigtool -i %s" % fname

	logging.debug("Running command: %s" % cmd)
	proc = subprocess.Popen(shlex.split(cmd), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
	out  = proc.communicate()

	for line in out[0].split("\n"):
		m = re.match(r"^Version: (\d+)$", line)

		if m is not None:
			return int(m.group(1))

	return -1

def getText():
	domain="current.cvd.clamav.net"

	logging.info("Querying '%s' for TXT record." % domain)
	a = dns.resolver.query(domain, 'TXT')

	if len(a) != 1:
		raise Exception("Answer does not contain expected number of responses.")

	logging.debug(a.rrset[0])
	return dict(zip(['clam', 'main', 'daily', 'x', 'y', 'z', 'safebrowsing', 'bytecode'], a.rrset[0].to_text().strip('"').split(":")))

def main():
	logging.basicConfig(format="%(asctime)s: %(levelname)-8s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.DEBUG)

	vals = getText()
	logging.debug(vals)

	for f in ['main', 'daily', 'bytecode']:
		updateFile(f, int(vals[f]));

def updateFile(fname, cur):
	absPath = "%s/%s.cvd" % (DBDIR, fname)
	old = 0

	if os.path.exists(absPath):
		if os.stat(absPath).st_size > 0:
			old = getLocalVersion(absPath)

			if old > 0:
				logging.debug("%s old: %d, current: %d" % (fname, old, cur))

				if old > 10:
					i = (old - 10)
				else:
					i = 0

				logging.info("Checking for '%s' cdiff files." % fname)
				while i <= cur:
					cdiff = "%s-%d.cdiff" % (fname, i)
					local = "%s/%s" % (DBDIR, cdiff)
					i += 1
	
					if os.path.exists(local) and os.stat(local).st_size > 0:
						logging.debug("Already have %s" % cdiff)
						continue

					fetch("%s/%s" % (MIRROR, cdiff), local)
			else:
				logging.debug("File %s version unknown. Skipping cdiffs." % absPath)
		else:
			logging.debug("File %s is zero sized. Skipping cdiffs." % absPath)
	else:
		logging.debug("File %s does not exist. Skipping cdiffs." % absPath)

	if cur == old:
		logging.debug("Already at the latest version of '%s.cvd'." % fname)
		return True

	tmpFile = "%s/%s.cvd.tmp" % (DBDIR, fname)
	fetch("%s/%s.cvd" % (MIRROR, fname), tmpFile)

	if os.path.exists(tmpFile) and os.stat(tmpFile).st_size > 0:
		logging.info("Moving file '%s' to '%s'" % (tmpFile, absPath))
		shutil.move(tmpFile, absPath)
	else:
		logging.debug("Temporary file %s is not valid. Deleting.")
		os.unlink(tmpFile)

if __name__ == "__main__":
	main()
