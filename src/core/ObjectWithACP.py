
import utaka.src.core.Object as Object
import utaka.src.accessControl.ObjectACP as ObjectACP
import utaka.src.accessControl.BucketACP as BucketACP
import utaka.src.logging.BucketLog as BucketLogging
import utaka.src.exceptions.ForbiddenException as ForbiddenException

def getObject(user, bucket, key, getMetadata, getData, byteRangeStart, byteRangeEnd, ifMatch, ifNotMatch, ifModifiedSince, ifNotModifiedSince, ifRange):
	if not ObjectACP.checkUserPermission(user, bucket, key, 'read'):
		raise ForbiddenException.AccessDeniedException()
	res = Object.getObject(bucket = bucket, key=key, getMetadata=getMetadata, getData=getData, byteRangeStart=byteRangeStart, byteRangeEnd=byteRangeEnd, ifMatch=ifMatch, ifNotMatch=ifNotMatch, ifModifiedSince=ifModifiedSince, ifNotModifiedSince=ifNotModifiedSince, ifRange=ifRange)
	BucketLogging.logKeyEvent(user, bucket, key, 'get')
	return res

def setObject(user, bucket, key, metadata, data, contentMd5, contentType, contentDisposition, contentEncoding, accessControlPolicy):
	if not ObjectACP.checkUserPermission(user, bucket, key, 'write'):
		raise ForbiddenException.AccessDeniedException()
	res = Object.setObject(userid = user, bucket=bucket, key=key, metadata=metadata, data=data, content_md5 = contentMd5, content_type=contentType, content_disposition=contentDisposition, content_encoding=contentEncoding)
	ObjectACP.setObjectACP(bucket, key, accessControlPolicy)
	BucketLogging.logKeyEvent(user, bucket, key, 'set', res[2])
	return res
	
def cloneObject(user, sourceBucket, sourceKey, destBucket, destKey, metadata, ifMatch, ifNotMatch, ifModifiedSince, ifNotModifiedSince, accessControlPolicy):
	if not ( ObjectACP.checkUserPermission(user, sourceBucket, sourceKey, 'read') and ObjectACP.checkUserPermission(user, destBucket, destKey, 'write') ):
		raise ForbiddenException.AccessDeniedException()
	res = Object.cloneObject(user, sourceBucket, sourceKey, destBucket, destKey, metadata, ifMatch, ifNotMatch, ifModifiedSince, ifNotModifiedSince)
	ObjectACP.setObjectACP(destBucket, destKey, accessControlPolicy)
	BucketLogging.logKeyEvent(user, sourceBucket, sourceKey, 'get')
	BucketLogging.logKeyEvent(user, destBucket, destKey, 'set', res[2])
	return res

def destroyObject(user, bucket, key):
	if not ObjectACP.checkUserPermission(user, bucket, key, 'write'):
		raise ForbiddenException.AccessDeniedException()
	Object.destroyObject(bucket=bucket, key=key)
	BucketLogging.logKeyEvent(user, bucket, key, 'delete')
	
def getObjectACP(user, bucket, key):
	if not ObjectACP.checkUserPermission(user, bucket, key, 'read_acp'):
		raise ForbiddenException.AccessDeniedException()
	res = ObjectACP.getObjectACP(bucket, key)
	BucketLogging.logKeyEvent(user, bucket, key, 'get_acp')
	return res

def setObjectACP(user, bucket, key, accessControlPolicy):
	if not ObjectACP.checkUserPermission(user, bucket, key, 'write_acp'):
		raise ForbiddenException.AccessDeniedException()
	ObjectACP.setObjectACP(bucket, key, accessControlPolicy)
	BucketLogging.logKeyEvent(user, bucket, key, 'set_acp')