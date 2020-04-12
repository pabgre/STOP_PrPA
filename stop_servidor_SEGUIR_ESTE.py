# -*- coding: utf-8 -*-
"""
Created on Sun Apr 12 09:32:31 2020

@author: ELISA
"""

# -*- coding: utf-8 -*-

'''
pongo con tres almohadillas los nuevos comentarios (###)
###
el userdata es un diccionario de partidas:
->en cada partida se guarda un diccionario con:
-->los nombres de los jugadores: diccionario con las respuestas
-->'info':diccionario con el estado de la partida y el alfabeto
###
los sleep deberían estar todos en el cliente, pues el servidor no puede
pararse ya que igual atiende a más partidas
'''

from paho.mqtt.client import Client
###from multiprocessing import Process,Lock ###no usamos multiprocessing
###from time import sleep ###no usamos el sleep en el server
from random import shuffle
import pickle

#broker="localhost"
broker="wild.mat.ucm.es"
choques="clients/estop6" #topic=choques+"/servidor...
###choques: para evitar colisiones en el broker en las pruebas

alfabeto=[chr(i) for i in range(97,123)] #65a91 para MAY, 97a123 para minusculas
shuffle(alfabeto) ###barajamos el alfabeto para que no salgan en orden

max_jugadores_partida=3
min_jugadores_partida=2

class Player:
    #Constructora
    def __init__(self, player_id, player_table):
        self.id = player_id #El id unico del jugador
        self.table = player_table #El tablero del jugador
        self.score = 0 #la puuntuacion actual del jugador. Por defecto 0

    #Funcion que calcula la puntuacion en base a los rivales
    def calculate_score(self, rivals):
        for key in self.table:
            filled = (self.table[key] != None) and (self.table[key] != "") #Comprobamos que este rellenado ese tema
            if (filled):
                unique = True
                #Buscamos si la palabra es unica o no para calcular la puntuacion
                for rival in rivals:
                    if (rival.id != self.id):
                        unique = (self.table[key] != rival.table[key])
                        if (not(unique)):
                            break
                if (unique):
                    self.score += 25 # 25 pts si es unica
                else:
                    self.score += 10 # 10 pts si esta repetida
        return (self.score) #Para comprobar que funciona

#
def calcula_puntos(ids,diccs,num_partida,userdata):
    '''
    calcula las puntuaciones cuando se le pasa:
    ids: lista de nombres de usuario
    diccs: lista de diccionarios con las respuestas de cada usuario
    num_partida de los usuarios
    '''
    puntuacionesR=[] #puntuaciones de la ronda
    ldp=[] #lista de Players
    print("\nRespuestas de la ronda:")
    for i in range(len(ids)):
        ldp.append(Player(ids[i],diccs[i]))
        print(ids[i],":",diccs[i])
    for i in range(len(ldp)):
        jugador=ldp[i]
        #p2.calculate_score([p1, p2]) ejemplo
        puntos=jugador.calculate_score(ldp)
        puntuacionesR.append(puntos)
    print("Puntuaciones de la ronda")
    puntuacionesTotales=[]
    for i in range(len(ids)):
        print(userdata[int(num_partida)][ids[i]])
        p=puntuacionesR[i]+userdata[int(num_partida)][ids[i]]['puntos']
        print(p)
        userdata[int(num_partida)][ids[i]]['puntos']=p
        puntuacionesTotales.append(p)
        print(ids[i],":",puntuacionesR[i],p)
    #publicamos resultados a los usuarios:
    mqttc.publish(choques+"/partidas/"+str(num_partida)+"/puntos",
                  payload=pickle.dumps([ids,puntuacionesR,puntuacionesTotales]))

#
def callback_partidas(mqttc, userdata, msg):
    spl=msg.topic.split("/") #['clients','estop','partidas','1','puntos']
    indice_partida=int(spl[3]) #1
    if (msg.payload==b"READY_YES") and (userdata[indice_partida]['info']['estado']==1):
        ###si el estado es en espera y llega el READY_YES, iniciamos la ronda
        letra=(userdata[indice_partida]['info']['alfabeto']).pop(0)
        userdata[indice_partida]['info']['estado']=2 ###estado: en juego
        for jugador in userdata[indice_partida]:
            mqttc.publish(choques+"/jugadores/"+jugador,payload="PLAY_"+letra)
    if msg.payload==b"STOP":
        userdata[indice_partida]['info']['estado']=3 ###estado: en recuento
        for jugador in userdata[indice_partida]:
            mqttc.publish(choques+"/jugadores/"+jugador,payload="STOP")
    elif len(spl)==5:
        if spl[4]!="puntos": #['clients','estop','partidas','1','jugador']
            mensaje=pickle.loads(msg.payload) #llega el diccionario entero
            ###con las respuestas {'comida':None,'pais':'marruecos'}
            for clave,valor in mensaje.items():
                userdata[indice_partida][spl[4]][clave]=valor
            userdata[indice_partida]['info']['confirmados']+=1
            cuantos=len(userdata[indice_partida])-1 ###cuantos jugadores
            if cuantos==userdata[indice_partida]['info']['confirmados']:
                ###cuando ha llegado la info de todos los jugadores,
                ###calculamos los puntos
                userdata[indice_partida]['info']['confirmados']=0
                ids=[]
                diccs=[]
                for clave,valor in userdata[indice_partida].items():
                    if clave!='info':
                        ids.append(clave)
                        diccs.append(valor)
                print("Entramos a calcular los puntos de la ronda")
                calcula_puntos(ids,diccs,spl[3],userdata)
        elif spl[4]=="puntos": #['clients','estop','partidas','1','puntos']
            ###se han publicado los puntos, y preparamos la siguiente ronda
            userdata[indice_partida]['info']['estado']=1 #estado: en espera
            for jugador in userdata[indice_partida]:
                mqttc.publish(choques+"/jugadores/"+jugador,payload="READY")    

def callback_jugadores(mqttc, userdata, msg):
    #maneja las desconexiones inesperadas de los jugadores
    #eliminandolos del diccionario del servidor
    spl=msg.topic.split("/") #['clients','estop','jugadores','nombre']
    if msg.payload==b"DISCONNECT":
        usuario=spl[3]
        for clave,valor in userdata.items():
            if usuario in valor:
                valor.pop(usuario)
                if len(valor)==1:
                    userdata.pop(clave)
                    break
        print("estop userdata",userdata)

def on_message(mqttc, userdata, msg):
    print("MESSAGE:", userdata, msg.topic, msg.qos, msg.payload, msg.retain)
    ###al final no usamos el on_message pues hemos definido todo en callbacks
    ###separadas para mayor claridad

#
def callback_solicitudes(mqttc, userdata, msg):
    #print("MESSAGE:", userdata, msg.topic, msg.qos, msg.payload, msg.retain)
    spl=msg.topic.split("/") #['clients','estop','solicitudes','jugador']
    if len(spl)==3: #['clients','estop','solicitudes']
        usuario=str(msg.payload)[2:-1] ###"qwe"
        if userdata=={}:
            #si no hay nadie aún, mete al usuario en la partida 1 directamente
            mqttc.publish(choques+"/jugadores/"+usuario,payload="NUEVA_PARTIDA 1")
            alf=alfabeto.copy() ###hacemos una copia del alfabeto
            ###inicializamos el userdata
            userdata[1]={"info":{'estado':0,'alfabeto':alf,'confirmados':0},
                         usuario:{'puntos':0}}
        else:
            #si hay alguna partida, deja al usuario elegir entre nueva o cargar
            partidas_disponibles=[]
            for clave,valor in userdata.items():
                if len(valor)<max_jugadores_partida+1:
                    partidas_disponibles.append(clave)
            mqttc.publish(choques+"/jugadores/"+usuario,
                          payload="NUEVA [0] o CARGAR "+str(partidas_disponibles))
    #
    #ahora manejamos la eleccion de partida del cada usuario
    ###l=len(choques+"/solicitudes/")
    if len(spl)==4: #['clients','estop','solicitudes','jugador']
        usuario=spl[3]
        if msg.payload==b"0":
            p_libre=1 ###buscamos qué partida está libre
            while p_libre in userdata.keys():
                p_libre+=1
            mqttc.publish(choques+"/jugadores/"+usuario,
                          payload="NUEVA_PARTIDA "+str(p_libre))
            alf=alfabeto.copy() ###hacemos una copia del alfabeto
            ###inicializamos el userdata
            userdata[p_libre]={"info":{'estado':0,'alfabeto':alf,'confirmados':0}
                               ,usuario:{'puntos':0}}
        else:
            indice_partida=int(str(msg.payload)[2:-1])
            userdata[indice_partida][usuario]={'puntos':0}
            #decidimos cuando empezar la partida, según los usuarios apuntados
            ###esto hay que mirarlo:
            if len(userdata[indice_partida])-1 < min_jugadores_partida:
                #no hay jugadores suficientes
                for jugador in userdata[indice_partida]:
                    mqttc.publish(choques+"/jugadores/"+jugador,payload="NOT_INOF")
            elif len(userdata[indice_partida])-1 == min_jugadores_partida:
                #ya hay jugadores suficientes
                #el sleep ha pasado al cliente
                userdata[indice_partida]['info']['estado']=1 #estado: en espera
                for jugador in userdata[indice_partida]:
                    mqttc.publish(choques+"/jugadores/"+jugador,payload="READY")
            else:
                #falta el caso en el que se conecta uno más tarde
                #de momento creo que es mejor que funcione como una partida
                #normal en la que todos los jugadores están desde el principio
                ###creo que esta eventualidad se maneja mejor desde el cliente
                pass
    #
    print("estop actual",userdata) #mostramos el diccionario tras cada mensaje
    #

#
def callback_servidor(mqttc, userdata, msg):
    #aceptamos conexiones
    #print("MESSAGE:", userdata, msg.topic, msg.qos, msg.payload, msg.retain)
    print("MESSAGE:", msg.topic, msg.payload)
    spl=msg.topic.split("/") #['clients','estop','servidor','nombre']
    if msg.payload==b"CONNECT_REQUEST":
        ###comprobamos que el usuario no está aún registrado
        ya_registrado=False
        usuario=spl[3]
        for clave,valor in userdata.items():
            if usuario in valor:
                ya_registrado=True
                break
        if (usuario=="") or (usuario=="info") or ya_registrado or (usuario=="puntos"):
            ###cosas que no aceptamos como nombre_usuario
            mqttc.publish(choques+"/servidor/exception",payload="USER_EXC")
        else:
            ###aceptamos al usuario
            mqttc.publish(msg.topic,payload="CONNECT_ACCEPT")
    print("estop userdata",userdata)

#

###

mqttc = Client(userdata={}) ###diccionario como userdata para la info del juego
###'info' indica el estado de la partida:
###estado: 0 es sin empezar,1 en espera,2 jugando,3 en recuento
###alfabeto: las letras que quedan por jugar, de inicio ya están desordenadas
###confirmados para tener una forma de ver si todos envian la info

#funciones callback:
#mqttc.on_publish = on_publish
mqttc.on_message = on_message
mqttc.message_callback_add(choques+"/jugadores/#", callback_jugadores)
mqttc.message_callback_add(choques+"/partidas/#", callback_partidas)
mqttc.message_callback_add(choques+"/servidor/#", callback_servidor)
mqttc.message_callback_add(choques+"/solicitudes/#", callback_solicitudes)

#will_set:
#ultimo mensaje que se envía si el Client se desconecta sin usar disconnect()
mqttc.will_set(choques+"/servidor",payload="SERVER_FAIL")

mqttc.connect(broker)

mqttc.publish(choques+"/servidor",payload="SERVER_READY")
print("SERVIDOR ACTIVO...")

#suscripciones iniciales del servidor
mqttc.subscribe(choques+"/servidor/#")
mqttc.subscribe(choques+"/solicitudes/#")
mqttc.subscribe(choques+"/jugadores/#")
mqttc.subscribe(choques+"/partidas/#")

mqttc.loop_forever()

###