#!/bin/bash
###############################################################################
# Clue Configuration Manager
#
# Test Setup module deploying source file on a remote system. Test process could be
# customized using the ollowing options:
#	-s = deploy resources located in 'src' folder
#	-p = install debian package if exists
#
# $Id: test-mod.sh 817 2016-09-03 08:45:24Z stefan $
###############################################################################

echo ; echo "------------------------------------------------------------------------------"
echo "Test deployment of resources related to [${MOD}] module.." ; echo ; sleep 2

# Set Remote system for deploying
setRemoteSystem "${SYS}"

if [ "${OPT}" = "" ] || [[ "${OPT}" = -*s* ]]; then
	if [ -d $SRCDIR ]; then
		/usr/bin/ssh $REMOTEUSER@$REMOTEHOST "mkdir -p /opt/clue/lib/python2.7/dist-packages/picam"
		/usr/bin/scp -r $SRCDIR/picam.py $REMOTEUSER@$REMOTEHOST:/opt/clue/lib/python2.7/dist-packages/picam
	fi
	if [ -d $SYSDIR ]; then
		/usr/bin/scp -r $SYSDIR/* $REMOTEUSER@$REMOTEHOST:/
	fi
fi

if [[ "${OPT}" = -*p* ]]; then
	if [ -f $DISTPATH/modules/${MOD} ]; then
		file="${MOD}"
		path="${DISTPATH}/modules/${MOD}"
	elif [ -f $DISTPATH/modules/${MOD}.deb ]; then
		file="${MOD}.deb"
		path="${DISTPATH}/modules/${MOD}.deb"
	elif [ -f $DISTPATH/modules/clue-${MOD}.deb ]; then
		file="clue-${MOD}.deb"
		path="${DISTPATH}/modules/clue-${MOD}.deb"
	else
		echo "Error (131): Module name or module file distribution could not be found: ${MOD}" ; echo
		exit 303
	fi

	if [ -f $path ]; then
		/usr/bin/scp -r $path $REMOTEUSER@$REMOTEHOST:/tmp/$file
		/usr/bin/ssh $REMOTEUSER@$REMOTEHOST "dpkg -i /tmp/$file ; rm -rf /tmp/$file"
	fi
fi