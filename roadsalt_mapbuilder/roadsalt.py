# -*- coding: utf-8 -*-
#
#  roadsalt.py
#
#  Authors:       Lais Baroni     <laisrbaroni@gmail.com> (1)
#                 Alvaro Bueno    <alvarobb10@gmail.com> (2)
#                 Irving Badolato <irvingbadolato@eng.uerj.br> (1)
#   
#  Copyright 2019 (1) CARTO/UERJ
#                 (2) IBM
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA. 


# Pacotes e modulos em uso
from qgis.core import *
from qgis.gui import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from qgis.analysis import *
from processing.algs.qgis.QgisAlgorithm import *
import processing
import sys
import os
import qgis.utils
import glob
import shutil
import time

# Secao dedicada as funcoes do plugin em desenvolvimento

def loadData(streets_filename, basins_filename, salt_filename = ''):
	return {"street" : QgsVectorLayer(streets_filename, ''),
	        "basin" : QgsVectorLayer(basins_filename, ''),
	        "salt" : QgsVectorLayer(salt_filename, '')}

def showData(filename, field = None, iface = None):
	if iface:
		layer = iface.addVectorLayer(filename, "", "ogr")
		renderer = QgsGraduatedSymbolRenderer() 
		renderer.setClassAttribute(field) 
		layer.setRenderer(renderer) 
		layer.renderer().updateClasses(layer, QgsGraduatedSymbolRenderer.Jenks, 5)
		layer.renderer().updateColorRamp(QgsGradientColorRamp(Qt.white, Qt.darkRed))
		iface.layerTreeView().refreshLayerSymbology(layer.id())
		iface.mapCanvas().refreshAllLayers()

def clear(dir_trabalho):
	path1 = os.path.join(dir_trabalho, "buffer_individuais")
	path2 = os.path.join(dir_trabalho, "bacias_individuais")
	filesToRemove1 = [os.path.join(path1,f1) for f1 in os.listdir(path1)]
	for f1 in filesToRemove1:
		os.remove(f1) 
	filesToRemove2 = [os.path.join(path2,f2) for f2 in os.listdir(path2)]
	for f2 in filesToRemove2:
		os.remove(f2) 
	os.rmdir(os.path.join(dir_trabalho, "bacias_individuais"))
	os.rmdir(os.path.join(dir_trabalho, "buffer_individuais"))

def stage1(vector, tam_buffer, unit="m"):		
	if unit=="m":
		mybuffer = tam_buffer
	if unit=="km":
		mybuffer = tam_buffer * 1000
	if unit=="mile":
		mybuffer = tam_buffer * 1609.34
	args = {'INPUT': vector,
		'DISTANCE': mybuffer,
		'SEGMENTS': 10,
		'DISSOLVE': True,
		'END_CAP_STYLE': 0,
		'JOIN_STYLE': 0,
		'MITER_LIMIT': 10,
		'OUTPUT': 'memory:buffer'}
	return processing.run("native:buffer",args)['OUTPUT']

def stage2(vector):
	args = {'INPUT': vector,
			'FIELD_NAME': 'IDapp',
			'FIELD_TYPE': 1,
			'FIELD_LENGTH': 10,
			'FIELD_PRECISION': 0,
			'NEW_FIELD': True,
			'FORMULA': '$id',
			'OUTPUT': 'memory:bacias'}
	return processing.run("qgis:fieldcalculator",args)['OUTPUT']

def stage3(entrada, dir_trabalho):
	args = {'INPUT': entrada,
			'FIELD': 'IDapp',
			'OUTPUT': os.path.join(dir_trabalho, 'bacias_individuais')}
	return processing.run("qgis:splitvectorlayer",args)['OUTPUT_LAYERS']

def stage4(vectorList, vector, dir_trabalho):
	os.mkdir(os.path.join(dir_trabalho, 'buffer_individuais'))
	result = []
	basepath = os.path.join(dir_trabalho, "buffer_individuais/buffer_")
	for item in vectorList:
		filename = basepath + os.path.basename( item )
		args = {'INPUT': item,
				'OVERLAY': vector,
				'OUTPUT': filename}
		result.append(processing.run("native:clip",args)['OUTPUT'] )
	return result

def stage5(entradas):
	args = {'LAYERS': entradas,
		'OUTPUT': 'memory:unidos'}
	return processing.run("native:mergevectorlayers",args)['OUTPUT']

def stage6(entrada):
	args = {'INPUT': entrada,
		'FIELD_NAME': 'areaBuf',
		'FIELD_TYPE': 0,
		'FIELD_LENGTH': 10,
		'FIELD_PRECISION': 2,
		'NEW_FIELD': True,
		'FORMULA': '$area',
		'OUTPUT': 'memory:buffer_area'}
	return processing.run("qgis:fieldcalculator",args)['OUTPUT']

def stage7(entrada):
	args = {'INPUT': entrada,
		'FIELD_NAME': 'areaBac',
		'FIELD_TYPE': 0,
		'FIELD_LENGTH': 10,
		'FIELD_PRECISION': 2,
		'NEW_FIELD': True,
		'FORMULA': '$area',
		'OUTPUT': 'memory:bacia_area'}
	return processing.run("qgis:fieldcalculator",args)['OUTPUT']

def stage8(entrada1, entrada2):
	args = {'INPUT': entrada1,
		'FIELD': 'IDapp',
		'INPUT_2': entrada2,
		'FIELD_2': 'IDapp',
		'FIELDS_TO_COPY': 'areaBuf',
		'METHOD': 0,
		'DISCARD_NONMATCHING': False,
		'PREFIX':'',
		'OUTPUT': 'memory:bacia_areas'}
	return processing.run("native:joinattributestable",args)['OUTPUT']

def stage9(entrada):
	args = {'INPUT': entrada,
		'FIELD_NAME': 'areaPor',
		'FIELD_TYPE': 0,
		'FIELD_LENGTH': 10,
		'FIELD_PRECISION': 4,
		'NEW_FIELD': True,
		'FORMULA': ' "areaBuf" / "areaBac" * 100 ',
		'OUTPUT': 'memory:result'}
	return processing.run("qgis:fieldcalculator",args)['OUTPUT']

def stage10(entrada, arq_destino):
	args = {'INPUT': entrada,
		'FIELD_NAME': 'areaPor',
		'FIELD_TYPE': 0,
		'FIELD_LENGTH': 10,
		'FIELD_PRECISION': 4,
		'NEW_FIELD': False,
		'FORMULA': ' if("areaPor" is null, 0, "areaPor") ',
		'OUTPUT': arq_destino}
	return processing.run("qgis:fieldcalculator",args)['OUTPUT']

def method_1(dir_trabalho, arq_entrada, arq_saida, opcoes):
	# Carrega os vetores [0]
	entrada = loadData(arq_entrada["street"], arq_entrada["basin"])
	# Cria o buffer de estradas [1]
	parte1 = stage1(entrada["street"], opcoes["buffer"], opcoes["unit"])
	# Cria o campo id nas bacias [2]
	parte2 = stage2(entrada["basin"])
	# Dividir as subbacias em arquivos diferentes [3]
	parte3 = stage3(parte2, dir_trabalho)
	# Cortar as bacias de acordo com a camada de buffer [4]
	parte4 = stage4(parte3, parte1, dir_trabalho)
	# Unir todos os recortes das estradas com buffer [5]
	parte5 = stage5(parte4)
	# Criar o campo com a area no arquivo de buffer [6]
	parte6 = stage6(parte5)
	# Criar o campo com a area no arquivo de bacias [7]
	parte7 = stage7(parte2)
	# Unir tabelas por atributo - unir o campo com a area da estrada no vetor de bacia [8]
	parte8 = stage8(parte7, parte6)
	# Criar campo com a porcentagem de area do buffer da estrada pelo poligono [9]
	parte9 = stage9(parte8)
	# Preencher campos vazios com 0 [10]
	stage10(parte9, arq_saida)
	# carrega resultado
	if "iface" in opcoes:
		showData(arq_saida, "areaPor", iface=opcoes["iface"])
	# Liberando a memoria
	entrada, parte1, parte2, parte3, parte4, parte5, parte6, parte7, parte8, parte9 = None, None, None, None, None, None, None, None, None, None
	# remove as pastas intermediarias criadas
	clear(dir_trabalho)

def stageA(entrada, valueField, dateField, start, end):
	features = entrada.getFeatures()
	acum = 0
	for feat in features:
		if feat[dateField] >= start and feat[dateField] <= end: 
			acum += feat[valueField]
	return acum

def stageB(lines, polygons):
	args = {'LINES': lines,
		'POLYGONS': polygons,
		'LEN_FIELD': 'tamEstr',
		'COUNT_FIELD': 'NEstr',
		'OUTPUT': "memory:result"}
	return processing.run("qgis:sumlinelengths", args)['OUTPUT']

def stageC(vectorLayer, const, arq_destino, length = "tonmile"):	
	if length=="galmile" or length=="tonmile":
		mylength = const * 0.000621371
	if length=="literkm" or length=="kgkm":
		mylength = const * 0.001
	args = {'INPUT': vectorLayer,
		'FIELD_NAME': 'qtd_sal',
		'FIELD_TYPE': 0,
		'FIELD_LENGTH': 10,
		'FIELD_PRECISION': 4,
		'NEW_FIELD': True,
		'FORMULA': '%f*"tamEstr"' % (mylength),
		'OUTPUT': arq_destino}
	final = processing.run("qgis:fieldcalculator", args)['OUTPUT']

def method_2(dir_trabalho, arq_entrada, arq_saida, opt):
	# Carrega os vetores e dado de sal [0]
	data = loadData(arq_entrada["street"], arq_entrada["basin"], arq_entrada["salt"])
	# Computa o acumulado de sal no intervalo [1]
	soma = stageA(data["salt"], opt["valueIdx"], opt["dateIdx"], opt["t0"], opt["t1"])
	# Conta o tamanho das estradas (em metros) dentro dos polígonos [2]	
	tamEstr = stageB(data["street"], data["basin"])
	# multiplicar a soma de sal com a quantidade de estradas [3]
	stageC(tamEstr, soma, arq_saida, opt["length"])
	# carrega resultado
	if "iface" in opt:
		showData(arq_saida, "qtd_sal", opt["iface"])
