#!/usr/bin/python
# -*- coding: utf-8 -*-
from openerp_rpc_cli import openerp_rpc_cli

import csv
import urllib2
import base64
import xmlrpclib
import os.path

class import_product_images(openerp_rpc_cli.OpenErpRpcCli):

	description = """
	This script takes a csv with columns id and path, containing product XML id's and image path respectively.
	It downloads the image for each product from the path and saves it to the product with respective xml id.
	The image path can be either a URL or a file system path.

	A file called done.txt will be created in the same directory as the CSV file, containing the XML IDs of all
	products that were processed. The next time this script is ran, it will check for a done file, and ignore
	any products that are in it.
	"""

	def set_arguments(self, parser):
		parser.add_argument('file_path', type=str, help='Path to the CSV file. Can be a local file path or a URL (http).')
		parser.add_argument('--path-prefix', type=str, help='Text to prefix to the values in the file path column')

	def do(self, args, conn):
		prod_obj = conn.get_model('product.product')
		imd_obj = conn.get_model('ir.model.data')

		# get path for done.txt - file containing xml ids of products that are already updated
		done_file_path = args.file_path.split('/')
		done_file_name = ['done', 'txt']
		done_file_name = '.'.join(done_file_name)
		done_file_path[-1] = done_file_name
		done_file_path = '/'.join(done_file_path)

		# make sure done.txt file exists already
		if not os.path.isfile(done_file_path):
			print 'Creating done file %s' % done_file_path
			d = open(done_file_path, 'w')
			d.write('')
			d.close()
		else:
			print 'Using done file %s' % done_file_path

		# open done.txt file to read already done product xml ids and append new ones
		with open(done_file_path, 'ra+') as done_file:
			done = map(lambda l: l.replace('\n', ''), done_file.readlines())

			# start reading CSV file
			with open(args.file_path, 'rb') as csv_file:
				dialect = csv.Sniffer().sniff(csv_file.read(1024))
				csv_file.seek(0)
				reader = csv.reader(csv_file, dialect)
				header = None
				row_count = 0

				# loop over csv rows
				for row in reader:

					row_count += 1

					# decode latin-1 for accents
					row = map(lambda r: r.decode('latin-1'), row)

					# save header row
					if header == None:
						header = row
						continue

					# data assertions
					assert all([col in header for col in ['id', 'path']]), 'Missing id or path columns from first csv row'

					# assign variables called pos_*columnName*
					for index in xrange(0, len(header)):
						exec('pos_%s = %s' % (header[index], index))

					# extract data from row
					prod_xml_id = row[pos_id]
					prod_path = (args.path_prefix or '') + row[pos_path]
					if not prod_path:
						continue

					# get xml id from prod_xml_id
					if '.' in prod_xml_id:
						prod_xml_id = prod_xml_id.split('.')[1]

					# skip products that were already imported
					if prod_xml_id in done:
						print 'Skipping %s' % prod_xml_id
						continue

					# convert xml id to db id
					imd_ids = imd_obj.search([('model', '=', 'product.product'), ('name', '=', prod_xml_id)])
					if not imd_ids:
						print row_count
						print 'Could not find xml id: %s' % prod_xml_id
						print ''
						continue 

					imd_res_id = imd_obj.read(imd_ids, ['res_id'])
					prod_id = imd_res_id[0]['res_id']

					# encode path
					try:
						prod_path = urllib2.quote(bytes(prod_path.replace('\\', '/').encode('utf-8')), safe=":/'")
					except UnicodeEncodeError as e:
						print row_count
						print 'URL encoding error for string: %s' % prod_path
						print 'Original path: %s' % row[pos_path]
						print unicode(e)
						print ''

					# get image and convert to base64
					try:
						image = None
						
						if prod_path[0:4] == 'http':
							response = urllib2.urlopen(prod_path)
							image = response.read()
							response.close()
						else:
							image_file = open(prod_path)
							image = image_file.read()
							image_file.close()

						image_base64 = base64.encodestring(image)
					except urllib2.URLError as e:
						print row_count
						print 'could not get image %s: %s' % (prod_path, unicode(e))
						print ''
						continue

					# write to openerp
					try:
						prod_obj.write(prod_id, {'image_medium': image_base64})
						done_file.write('%s\n' % prod_xml_id)
						print 'updated img for prod id: %s, xml id: %s' % (prod_id, prod_xml_id)
					except xmlrpclib.Fault as e:
						print row_count
						print 'rpc error while uploading: %s' % unicode(e)
						print ''

				# close csv file
				print 'finished uploading %s product images' % row_count

			# close done file

import_product_images()
