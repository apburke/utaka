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

from mod_python import apache
import xml.dom.minidom
import utaka.src.core.BucketWithACPAndLog as Bucket
import utaka.src.accessControl.BucketACP as BucketACP
import utaka.src.accessControl.AcpXml as AcpXml
import utaka.src.exceptions.MethodNotAllowedException as MethodNotAllowedException
import utaka.src.exceptions.BadRequestException as BadRequestException

class UtakaBucket:

	def __init__(self, utakaReq):
		self.utakaReq = utakaReq

	def handleRequest(self):
		if 'torrent' in self.utakaReq.subresources:
			raise BadRequestException.RequestTorrentOfBucketErrorException()
		if 'acl' in self.utakaReq.subresources:
			if self.utakaReq.req.method == 'GET':
				operation = self.__getAclOperation
			elif self.utakaReq.req.method == 'PUT':
				operation = self.__putAclOperation
			else:
				raise MethodNotAllowedException.ACLMethodNotAllowedException(self.utakaReq.req.method)
		elif 'logging' in self.utakaReq.subresources:
			if self.utakaReq.req.method == 'GET':
				operation = self.__getLoggingOperation
			elif self.utakaReq.req.method == 'PUT':
				raise MethodNotAllowedException.BucketLogginStatusMethodException
			else:
				raise MethodNotAllowedException.LoggingStatusMethodNotAllowedException(self.utakaReq.req.method)
		elif self.utakaReq.req.method == 'GET':
			operation = self.__getOperation
		elif self.utakaReq.req.method == 'PUT':
			operation = self.__putOperation
		elif self.utakaReq.req.method == 'DELETE':
			operation = self.__deleteOperation
		elif self.utakaReq.req.method == 'POST':
			operation = self.__postOperation
		elif self.utakaReq.req.method == 'COPY':
			operation = self.__copyOperation
		else:
			raise MethodNotAllowedException.BucketMethodNotAllowedException(self.utakaReq.req.method)
		return operation()


	def __copyOperation(self):
		pass


	def __postOperation(self):
		pass


	def __deleteOperation(self):
		result = Bucket.destroyBucket(bucket=self.utakaReq.bucket, user=self.utakaReq.user)
		self.utakaReq.req.status = 204


	def __putOperation(self):
		cannedACL = self.utakaReq.customHeaderTable.get('acl', 'private')
		acp = {}
		acp['owner'] = {'userid':self.utakaReq.user}
		acl = [{'grantee':{'userid':self.utakaReq.user}, 'permission':'FULL_CONTROL'}]
		if cannedACL == 'public-read':
			acl.append({'grantee':{'userid':1}, 'permission':'read'})
		elif cannedACL == 'public-read-write':
			acl.append({'grantee':{'userid':1}, 'permission':'read'})
			acl.append({'grantee':{'userid':1}, 'permission':'write'})
		elif cannedACL == 'authenticated-read':
			acl.append({'grantee':{'userid':2}, 'permission':'read'})
		elif cannedACL != 'private':
			'''throw error'''
		acp['acl'] = acl
		result = Bucket.setBucket(bucket = self.utakaReq.bucket, user = self.utakaReq.user, accessControlPolicy = acp)


	def __getOperation(self):
		getBucketParams = {'name':self.utakaReq.bucket}
		for param in 'prefix', 'marker', 'max-keys', 'delimiter':
			if param in self.utakaReq.subresources:
				getBucketParams[param] = self.utakaReq.subresources[param][0]
		if 'max-keys' not in getBucketParams:
			getBucketParams['max-keys'] = 1000
		res = Bucket.getBucket(bucket = self.utakaReq.bucket, user = self.utakaReq.user,
					prefix = getBucketParams.get('prefix'), marker = getBucketParams.get('marker'),
					maxKeys = getBucketParams.get('max-keys'), delimiter = getBucketParams.get('delimiter'))
		getBucketParams['isTruncated'] = str(res[2])
		self.utakaReq.req.content_type = 'application/xml'
		self.utakaReq.write(self.__getXMLResponse(getBucketParams, res[0], res[1]))

	def __putLoggingOperation(self):
		pass


	def __getLoggingOperation(self):
		Bucket.getBucketLogStatus(user=self.utakaReq.user, bucket=self.utakaReq.bucket)



	def __putAclOperation(self):
		#READ BODY
		acp = AcpXml.fromXML(self.utakaReq.req.read())
		Bucket.setBucketACP(user=self.utakaReq.user, bucket=self.utakaReq.bucket, accessControlPolicy=acp)
		pass


	def __getAclOperation(self):
		bucket_acp = Bucket.getBucketACP(bucket=self.utakaReq.bucket, user=self.utakaReq.user)
		if len(bucket_acp) == 0:
			'''bucket not found, throw error'''
		else:
			self.utakaReq.req.content_type = 'applicaton/xml'
			self.utakaReq.write(AcpXml.toXML(bucket_acp))


	def __getXMLResponse(self, bucketDictionary, contentDictionaryList, commonPrefixesList):

		doc = xml.dom.minidom.Document()
		listBucketEl = doc.createElement("ListBucketResult")
		listBucketEl.setAttribute('xmlns', 'http://s3.amazonaws.com/doc/2006-03-01/')

		nameEl = doc.createElement("Name")
		nameEl.appendChild(doc.createTextNode(bucketDictionary.get('name')))
		listBucketEl.appendChild(nameEl)

		prefixEl = doc.createElement("Prefix")
		prefixEl.appendChild(doc.createTextNode(bucketDictionary.get('prefix', '')))
		listBucketEl.appendChild(prefixEl)

		markerEl = doc.createElement("Marker")
		markerEl.appendChild(doc.createTextNode(bucketDictionary.get('marker', '')))
		listBucketEl.appendChild(markerEl)

		maxkeysEl = doc.createElement("MaxKeys")
		maxkeysEl.appendChild(doc.createTextNode(str(bucketDictionary.get('max-keys', ''))))
		listBucketEl.appendChild(maxkeysEl)

		truncatedEl= doc.createElement("IsTruncated")
		truncatedEl.appendChild(doc.createTextNode(bucketDictionary.get('isTruncated', '')))
		listBucketEl.appendChild(truncatedEl)

		for val in contentDictionaryList:
			contentsEl = doc.createElement("Contents")
			keyEl = doc.createElement("Key")
			keyEl.appendChild(doc.createTextNode(val['key']))
			contentsEl.appendChild(keyEl)

			lastModifiedEl = doc.createElement("LastModified")
			lastModifiedEl.appendChild(doc.createTextNode(val['lastModified']))
			contentsEl.appendChild(lastModifiedEl)

			eTagEl = doc.createElement("ETag")
			eTagEl.appendChild(doc.createTextNode(val['eTag']))
			contentsEl.appendChild(eTagEl)

			sizeEl = doc.createElement("Size")
			sizeEl.appendChild(doc.createTextNode(str(val['size'])))
			contentsEl.appendChild(sizeEl)

			storageClassEl = doc.createElement("StorageClass")
			storageClassEl.appendChild(doc.createTextNode("STANDARD"))
			contentsEl.appendChild(storageClassEl)

			ownerEl = doc.createElement("Owner")
			ownerIdEl = doc.createElement("ID")
			ownerIdEl.appendChild(doc.createTextNode(str(val['owner']['id'])))
			ownerNameEl = doc.createElement("DisplayName")
			ownerNameEl.appendChild(doc.createTextNode(val['owner']['name']))
			ownerEl.appendChild(ownerIdEl)
			ownerEl.appendChild(ownerNameEl)
			contentsEl.appendChild(ownerEl)
			listBucketEl.appendChild(contentsEl)

		if commonPrefixesList:
			commonPrefixesEl = doc.createElement("CommonPrefixes")
			for val in commonPrefixesList:
				commonPrefixEl = doc.createElement("Prefix")
				commonPrefixEl.appendChild(doc.createTextNode(val))
				commonPrefixesEl.appendChild(commonPrefixEl)
			listBucketEl.appendChild(commonPrefixesEl)

		doc.appendChild(listBucketEl)
		return doc.toxml('utf-8')