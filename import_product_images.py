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
	Takes a csv with columns id and url, containing product XML id's and image url respectively.
	Then downloads the image for each product from the url and saves it to the product with respective
	xml_id in OE
	"""

	def set_arguments(self, parser):
		parser.add_argument('file_path', type=str, help='Path to the CSV file. Columns should be db-id/name/url')
		parser.add_argument('--url-prefix', type=str, help='Text to prefix to the values in the url column')

	def do(self, args, conn):
		prod_obj = conn.get_model('product.product')
		imd_obj = conn.get_model('ir.model.data')

		# get path for done.txt - file containing xml ids of products that are already updated
		done_file_path = args.file_path.split('/')
		done_file_name = ['done', 'txt']
		done_file_name = '.'.join(done_file_name)
		done_file_path[-1] = done_file_name
		done_file_path = '/'.join(done_file_path)

		print ''
		print 'Preparing to upload images to products'
		print ''

		# make sure done.txt file exists already
		if not os.path.isfile(done_file_path):
			print 'Creating file %s' % done_file_path
			d = open(done_file_path, 'w')
			d.write('')
			d.close()

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
					assert all([col in header for col in ['id', 'url']]), 'Missing id or url columns from first csv row'

					# assign variables called pos_*columnName*
					for index in xrange(0, len(header)):
						exec('pos_%s = %s' % (header[index], index))

					# extract data from row
					prod_xml_id = row[pos_id]
					prod_path = (args.url_prefix or '') + row[pos_url]
					if not prod_path:
						continue

					# get xml id from prod_xml_id
					if '.' in prod_xml_id:
						prod_xml_id = prod_xml_id.split('.')[1]

					# skip products that were already imported
					if prod_xml_id in done:
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

					# encode url
					try:
						prod_path = urllib2.quote(bytes(prod_path.replace('\\', '/').encode('utf-8')), safe=":/'")
					except UnicodeEncodeError as e:
						print row_count
						print 'URL encoding error for string: %s' % prod_path
						print 'Original url: %s' % row[pos_url]
						print unicode(e)
						print ''

					# get image and convert to base64
					try:
						image = None
						
						if 'http' in prod_path or 'ftp' in prod_path:
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
						print row_count
						print 'updated img for prod id: %s, xml id: %s' % (prod_id, prod_xml_id)
						print ''
					except xmlrpclib.Fault as e:
						print row_count
						print 'rpc error while uploading: %s' % unicode(e)
						print ''

				# close csv file
				print 'DONE ALL %s' % row_count

			# close done file

		print 'bye'

import_product_images()
