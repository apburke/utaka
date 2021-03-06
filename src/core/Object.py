#!/usr/bin/python
# -*- coding: utf-8 -*-

#Copyright 2009 Humanitarian International Services Group
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

from MySQLdb import escape_string
import utaka.src.exceptions.NotFoundException as NotFoundException
import utaka.src.exceptions.BadRequestException as BadRequestException
import utaka.src.exceptions.InternalErrorException as InternalErrorException
import utaka.src.exceptions.NotModifiedException as NotModifiedException
import utaka.src.exceptions.PreconditionFailedException as PreconditionFailedException
from utaka.src.dataAccess.Connection import Connection
from utaka.src.core.Bucket import _verifyBucket
import utaka.src.Config as Config
import hashlib
import errno
import md5
import time
import os

'''
getObject
	params:
		str bucket
		str key
		bool getMetadata
		bool getData
		int byteRangeStart - optional
		int byteRangeEnd - optional
		str ifMatch - optional
		str ifNotMatch - optional
		datetime ifModifiedSince - optional
		datetime ifNotModifiedSince - optional
		str or datetime ifRange - optional
	returns:
		dict
			str key
			dict owner - userid, username
			str eTag
			str lastModified
			dict metadata - conditional
			str data - conditional
			str size
			str content-type
			str content-encoding - conditional
			str content-disposition - conditional
			str content-range - conditional
'''
def getObject(bucket, key, getMetadata, getData, byteRangeStart = None, byteRangeEnd = None, ifMatch = None, ifNotMatch = None, ifModifiedSince = None, ifNotModifiedSince = None, ifRange = None):
	'''returns object'''

	conn = Connection()
	try:
		#Validate the bucket
		_verifyBucket(conn, bucket, True)

		#Check for object and get information from database
		query = "SELECT o.object, o.bucket, o.hashfield, o.object_create_time, o.eTag, o.object_mod_time, o.size, o.content_type, o.content_encoding, o.content_disposition, o.userid, u.username FROM object as o, user as u WHERE o.bucket = %s AND o.object = %s AND o.userid = u.userid"
		result = conn.executeStatement(query, (escape_string(str(bucket)), escape_string(str(key))))
		if len(result) == 0:
				raise NotFoundException.NoSuchKeyException(bucket, key)
		result = result[0]


		#if _passPrecondition(str(result[4]), str(result[5]), str(ifMatch), str(ifNotMatch), str(ifModifiedSince), str(ifNotModifiedSince), str(ifRange)) == False:
		#    byteRangeStart = None
		#    byteRangeEnd = None


		#Get metadata from database
		query = "SELECT type, value FROM object_metadata WHERE bucket = %s AND object = %s"
		metadata = conn.executeStatement(query, (escape_string(str(bucket)), escape_string(str(key))))
	except:
		conn.cancelAndClose()
		raise
	else:
		conn.close()

	metadataDict = {}
	for tag in metadata:
		metadataDict[str(tag[0])] = unicode(tag[1], encoding='utf8')

	content_range = {}
	size = 0
	hashfield = str(result[2])
	if getData:
		#Get data from filesystem and build content_range
		path = Config.get('common','filesystem_path')
		path += str(bucket)
		path += "/"+hashfield[0:3]+"/"+hashfield[3:6]+"/"+hashfield[6:9]+"/"+hashfield
		fileReader = open(path, 'rb')
		try:
			data = ""
			if byteRangeStart != None and byteRangeStart > 0:
				fileReader.seek(byteRangeStart)
				content_range['start'] = byteRangeStart
				if byteRangeEnd != None and byteRangeEnd > byteRangeStart:
					data = fileReader.read(byteRangeEnd-byteRangeStart)
					content_range['end'] = fileReader.tell()
					fileReader.read()
					content_range['total'] = fileReader.tell()
					size = byteRangeEnd-byteRangeStart
				else:
					data = fileReader.read()
					content_range['end'] = fileReader.tell()
					content_range['total'] = fileReader.tell()
					size = content_range['total']
			else:
				if byteRangeEnd != None:
					content_range['start'] = 0
					data = fileReader.read(byteRangeEnd)
					content_range['end'] = fileReader.tell()
					fileReader.read()
					content_range['total'] = fileReader.tell()
					size = byteRangeEnd
				else:
					data = fileReader.read()
					size = fileReader.tell()
		finally:
			fileReader.close()
		#print data

		if content_range.has_key('start'):
			content_range['string'] = str(content_range['start'])+"-"+str(content_range['end'])+"/"+str(content_range['total'])

	returnDict = {'key':str(result[0]),
	              'bucket':str(result[1]),
	              'hash':hashfield,
	              'creationTime':((result[3]).isoformat('T') + 'Z'),
	              'eTag':str(result[4]),
	              'lastModified':((result[5]).isoformat('T') + 'Z'),
	              'size':size,
	              'content-type':str(result[7]),
	              'owner':{'id':int(result[10]),
	              'name':unicode(result[11], encoding='utf8')}}
	if str(result[8]) != "" and result[8] != None:
		returnDict['content-encoding'] = str(result[8])
	if str(result[9]) != "" and result[9] != None:
		returnDict['content-disposition'] = str(result[9])
	if content_range.has_key('string'):
		returnDict['content-range'] = content_range['string']
	if getMetadata:
		returnDict['metadata'] = metadataDict
	if getData:
		returnDict['data'] = data

	return returnDict





'''
setObject
	params:
		userid
		bucket
		key
		metadata
		data
		content_md5 - optional
		content_type - optional
		content_disposition - optional
		content_encoding - optional
	returns:

'''
def setObject(userid, bucket, key, metadata, data, content_md5 = None, content_type = None, content_disposition = None, content_encoding = None):
	'''setObject'''

	if not userid:
		userid = 1
	hashString = None
	conn = Connection()
	try:

		#Validate the bucket
		_verifyBucket(conn, bucket, userid, True)

		#Check for object and get information from database
		calculatedMD5 = md5.new(data)
		calculatedMD5HexDigest = calculatedMD5.hexdigest()
		if content_md5 != None and content_md5 != calculatedMD5HexDigest:
			raise BadRequestException.BadDigestException(content_md5, calculatedMD5HexDigest)

		#Generate hashfield
		hashfield = hashlib.sha1()
		hashfield.update(key)
		hashfieldHexDigest = ''
		success = False
		query = "SELECT COUNT(*) FROM object WHERE hashfield = %s"
		attemptedHashfieldList = []
		for i in range(3):
			hashfield.update(str(time.time()))
			hashfieldHexDigest = hashfield.hexdigest()
			attemptedHashfieldList.append(str(hashfieldHexDigest))
			count = conn.executeStatement(query, (str(hashfieldHexDigest)))[0][0]
			if count == 0:
				success = True
				break

		if success == False:
			raise InternalErrorException.HashfieldCollisionErrorException(attemptedHashfieldList)

		#Get size of file
		size = len(data)
		if content_type == None:
			content_type = "binary/octet-stream"
		if content_encoding == None:
			content_encoding = ""
		if content_disposition == None:
			content_disposition = ""

		#Build metadata query
		metadataQuery = ""
		if metadata != None and metadata != {}:
			metadataQuery = "INSERT INTO object_metadata (bucket, object, type, value) VALUES ("+"'"
			for tag, value in metadata.iteritems():
				if type(value) == str or type(value) == unicode:
					value = value.encode('utf8')
				else:
					value = str(value)
				metadataQuery += escape_string(str(bucket))+"', '"+escape_string(str(key))+"', '"+escape_string(tag)+"', '"+escape_string(value)+"'), ('"
			metadataQuery = metadataQuery[0:-4]

		#Write to database and filesystem
		result = conn.executeStatement("SELECT hashfield FROM object WHERE bucket = %s AND object = %s", (escape_string(str(bucket)), escape_string(str(key))))
		if len(result) > 0:
			hashString = result[0][0]
			path = Config.get('common','filesystem_path')
			path += str(bucket)
			path += "/"+hashString[0:3]+"/"+hashString[3:6]+"/"+hashString[6:9]
			os.remove(path+"/"+hashString)
			try:
				os.removedirs(path)
			except OSError, e:
				if e.errno != errno.ENOTEMPTY:
					raise
			hashString = str(hashfieldHexDigest)
			query = "UPDATE object SET userid = %s, hashfield = %s, eTag = %s, object_mod_time = NOW(), size = %s, content_type = %s, content_encoding = %s, content_disposition = %s WHERE bucket = %s AND object = %s"
			conn.executeStatement(query, (int(userid), hashString, str(calculatedMD5HexDigest), int(size), escape_string(str(content_type)), escape_string(str(content_encoding)), escape_string(str(content_disposition)), escape_string(str(bucket)), escape_string(str(key))))
			conn.executeStatement("DELETE FROM object_metadata WHERE bucket = %s AND object = %s", (escape_string(str(bucket)), escape_string(str(key))))
		else:
			query = "INSERT INTO object (userid, object, bucket, hashfield, object_create_time, eTag, object_mod_time, size, content_type, content_encoding, content_disposition) VALUES (%s, %s, %s, %s, NOW(), %s, NOW(), %s, %s, %s, %s)"
			hashString = str(hashfieldHexDigest)
			conn.executeStatement(query, (int(userid), escape_string(str(key)), escape_string(str(bucket)), hashString, str(calculatedMD5HexDigest), int(size), escape_string(str(content_type)), escape_string(str(content_encoding)), escape_string(str(content_disposition))))
		if metadataQuery != "":
			conn.executeStatement(metadataQuery, ())
	except:
		conn.cancelAndClose()
		raise
	conn.close()
	path = Config.get('common','filesystem_path')
	path += str(bucket)
	path += "/"+hashString[0:3]+"/"+hashString[3:6]+"/"+hashString[6:9]+"/"
	os.makedirs(path)
	path += hashString
	fileReader = open(path, 'wb')
	try:
		fileReader.write(data)
	finally:
		fileReader.close()
	return content_type, str(calculatedMD5HexDigest), hashString





'''
cloneObject
	params:
		str sourceKey
		str sourceBucket
		str destinationKey
		str destinationBucket
		int userid
		dict metadata - optional
		str ifMatch - optional
		str ifNotMatch - optional
		datetime ifModifiedSince - optional
		datetime ifNotModifiedSince - optional
	throws:
		InvalidKeyName
		InvalidBucketName
		KeyNotFound
		BucketNotFound
		UserNotFound
		PreconditionFailed
'''
def cloneObject(userid, sourceBucket, sourceKey, destinationBucket, destinationKey, metadata = None, ifMatch = None, ifNotMatch = None, ifModifiedSince = None, ifNotModifiedSince = None):
	'''clone object'''
	original = getObject(sourceBucket, sourceKey, True, True, None, None, ifMatch, ifNotMatch, ifModifiedSince, ifNotModifiedSince)
	if metadata != None:
		original['metadata'] = metadata
	if original.has_key('content-disposition'):
		content_disposition = original('content-disposition')
	else:
		content_disposition = None
	if original.has_key('content-encoding'):
		content_encoding = original['content-encoding']
	else:
		content_encoding = None
	return setObject(userid, destinationBucket, destinationKey, original['metadata'], original['data'], original['eTag'], original['content-type'], content_disposition, content_encoding)





'''
destroyObject
	params:
		str key
		str bucket
		str user
	throws:
		InvalidKeyName
		InvalidBucketName
		InvalidUserName
		KeyNotFound
		BucketNotFound
		UserNotFound
'''
def destroyObject(bucket, key):
	'''destroy's object'''

	conn = Connection()
	try:
		#Validate the bucket
		_verifyBucket(conn, bucket, True)

		#Check for object and get information from database
		query = "SELECT hashfield FROM object WHERE bucket = %s AND object = %s"
		result = conn.executeStatement(query, (escape_string(str(bucket)), escape_string(str(key))))
		if len(result) == 0:
			raise NotFoundException.NoSuchKeyException(bucket, key)

		#Delete the object from the database and the filesystem
		query = "DELETE FROM object_metadata WHERE bucket = %s AND object = %s"
		conn.executeStatement(query, (escape_string(str(bucket)), escape_string(str(key))))
		query = "DELETE FROM object WHERE bucket = %s AND object = %s"
		conn.executeStatement(query, (escape_string(str(bucket)), escape_string(str(key))))
	except:
		conn.cancelAndClose()
		raise
	conn.close()
	hashString = result[0][0]
	path = Config.get('common','filesystem_path')
	path += str(bucket)
	path += "/"+hashString[0:3]+"/"+hashString[3:6]+"/"+hashString[6:9]
	os.remove(path+"/"+hashString)
	try:
		os.removedirs(path)
	except OSError, e:
		if e.errno != errno.ENOTEMPTY:
			raise

def _passPrecondition(eTag, objectModTime, ifMatch, ifNotMatch, ifModifiedSince, ifNotModifiedSince, ifRange):
	import re
	dateRe = r"^[0-9]{4}(-[0-9]{2}){2}.[0-9]{2}(:[0-9]{2}){2}$"
	if ifMatch != "None" and eTag != "None" and eTag != ifMatch:
		raise PreconditionFailedException.IfMatchFailedException()
	if ifNotMatch != "None" and eTag != "None" and eTag == ifNotMatch:
		raise NotModifiedException.NotModifiedException()
	if ifModifiedSince != "None" and objectModTime != "None" and ifModifiedSince >= objectModTime:
		raise NotModifiedException.NotModifiedException()
	if ifNotModifiedSince != "None" and objectModTime != "None" and ifNotModifiedSince < objectModTime:
		raise PreconditionFailedException.IfUnmodifiedSinceFailedException()
	if eTag != "None" and ifRange != "None" and re.search(dateRe, ifRange) == None and eTag != ifRange:
		return False
	if objectModTime != "None" and ifRange != "None" and re.search(dateRe, ifRange) != None and ifRange < objectModTime:
		return False
	return True


if __name__ == '__main__':
    pass
    #setObject(3, 'billt.test', '/setTest1.txt', {'unicode':u'¥É∫'}, u"This is a üñîçø∂é test!")
    #getObject(3, 'billt.test', '/setTest.txt', None, True, None, None, None, None, None, None, None)
    #print getObject(3, 'billt.test', '/setTest1.txt', True, True, None, None, None, None, None, None, None)
    #print getObject(3, 'billt.test', '/setTest1.txt', True, True, 4, 10, None, None, None, None, None)
    #setObject(3, 'billt.test', '/setTest1.txt', {}, "This is a test!")
    #setObject(3, 'billt.test', '/setTest1.txt', {'unicode':u'¥É∫'}, "This is a üñîçø∂é test!")
    #getObject(3, 'billt.test', '/setTest.txt', None, True, None, None, None, None, None, None, None)
    #print getObject(3, 'billt.test', '/setTest1.txt', True, True, None, None, None, None, None, None, None)
    #print getObject(3, 'billt.test', '/setTest1.txt', True, True, 4, 10, None, None, None, None, None)
    #destroyObject(3, 'billt.test', '/setTest1.txt')
    #destroyObject(3, 'billt.test', '/Still Alive.mp3.bak')
    #cloneObject(3, 'billt.test', '/Still Alive.mp3', 'billt.test', '/Still Alive.mp3.bak', None, '01f4f497a00b333f082edd205104de20')
