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


'''
Created on Jul 10, 2009

@author: Andrew
'''


from utaka.src.dataAccess.Connection import Connection
import utaka.src.exceptions.NotFoundException as NotFoundException
import utaka.src.exceptions.InternalErrorException as InternalErrorException


'''
getBucketACP
	params:
		str bucket
	returns:
		{owner : {userid, username}, acl : [{grantee:{userid, username}, permission}]}
	raises:
		NoSuchBucketException
'''
def getBucketACP(bucket):
	'''returns dictionary representation of the bucket's access control policy'''
	conn = Connection(useDictCursor = True)
	try:
		rs = conn.executeStatement('''SELECT userid, username, 'owner' as permission
			FROM user JOIN bucket USING(userid) WHERE bucket = %s
			UNION
			SELECT userid, username, permission
			FROM bucket_permission JOIN user USING(userid)
			WHERE bucket = %s''', (bucket, bucket))
	finally:
		conn.close()
	acp = {}
	if len(rs) > 0:
		acp['owner'] = {'userid':rs[0]['userid'], 'username':rs[0]['username']}
		acp['acl'] = []
		for grant in rs[1:]:
			acp['acl'].append({'grantee':{'userid':grant['userid'], 'username':grant['username']}, 'permission':grant['permission']})
		return acp
	else:
		raise NotFoundException.NoSuchBucketException(bucket)


'''
setBucketACP
	params:
		bucket
		accessControlPolicy: {owner : {userid, username}, acl : [{grantee:{userid, username}, permission}]}
'''
def setBucketACP(bucket, accessControlPolicy):
	'''resets a bucket's acp to the passed parameter'''
	conn = Connection()
	try:
		removeString = 'delete from bucket_permission where bucket = %s'
		insertString = 'insert into bucket_permission (userid, bucket, permission) VALUES '
		aclWildcardList = []
		aclValueList = []
		for entry in accessControlPolicy['acl']:
			aclWildcardList.append('(%s, %s, %s)')
			aclValueList.append(entry['grantee']['userid'])
			aclValueList.append(bucket)
			aclValueList.append(entry['permission'])
		insertString += ', '.join(aclWildcardList)
		removeRS = conn.executeStatement(removeString, (bucket,))
		insertRS = conn.executeStatement(insertString, aclValueList)
	except:
		conn.cancelAndClose()
		raise
	else:
		conn.close()


'''
checkUserPermission
	params:
		user
		bucket
		action - read, write, destroy, write_log_status, read_log_status, read_acp, write_acp
	returns:
		bool permitted
'''
def checkUserPermission(user, bucket, action):
	'''checks if a user is permitted to perform action on bucket'''
	if action in ('write_log_status', 'read_log_status', 'destroy'):
		if not user:
			return False
		else:
			conn = Connection()
			try:
				result = conn.executeStatement('SELECT userid from bucket where bucket = %s', (bucket,))
			finally:
				conn.close()
			if len(result) == 0:
				raise NotFoundException.NoSuchBucketException(bucket)
			else:
				return result[0][0] == user

	elif action in ('read', 'write', 'read_acp', 'write_acp'):
		conn = Connection()
		try:
			if user:
				result = conn.executeStatement('''SELECT (SELECT COUNT(*) FROM bucket WHERE bucket = %s) +
					(SELECT COUNT(*) FROM bucket_permission WHERE userid IN(2, %s) and bucket = %s and permission IN(%s, "full_control"))''', (bucket, user, bucket, action))
			else:
				result = conn.executeStatement('''SELECT (SELECT COUNT(*) FROM bucket WHERE bucket = %s) +
					(SELECT COUNT(*) FROM bucket_permission WHERE userid = 1 and bucket = %s and permission IN(%s, 'full_control'))''', (bucket, bucket, action))
		finally:
			conn.close()
		if result[0][0] == 0:
			raise NotFoundException.NoSuchBucketException(bucket)
		else:
			return result[0][0] > 1

	else:
		raise InternalErrorException.BadArgumentException('action', str(action),
		  'Invalid action for BucketACP.checkUserPermission: action must be IN ("write_log_status", "read_log_status", "destroy", "write", "read", "write_acp", "read_acp").')




