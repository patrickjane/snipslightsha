#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# Snips Lights + Homeassistant
# -----------------------------------------------------------------------------
# Copyright 2019 Patrick Fial
# -----------------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and 
# associated documentation files (the "Software"), to deal in the Software without restriction, 
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial 
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT 
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. 
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE 
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------

import io
import toml
import requests
from os import environ

from snipsTools import SnipsConfigParser
from hermes_python.hermes import Hermes
from hermes_python.ontology import *

# -----------------------------------------------------------------------------
# global definitions (home assistant service URLs)
# -----------------------------------------------------------------------------

HASS_LIGHTS_ON_SVC = "/api/services/light/turn_on"
HASS_LIGHTS_OFF_SVC = "/api/services/light/turn_off"
HASS_GROUP_ON_SVC = "/api/services/homeassistant/turn_on"
HASS_GROUP_OFF_SVC = "/api/services/homeassistant/turn_off"
HASS_AUTOMATION_ON_SVC = "/api/services/automation/turn_on"
HASS_AUTOMATION_OFF_SVC = "/api/services/automation/turn_off"

# -----------------------------------------------------------------------------
# class App
# -----------------------------------------------------------------------------

class App(object):

    # -------------------------------------------------------------------------
    # ctor

    def __init__(self, debug = False):

        self.debug = debug
        self.enable_confirmation = False

        # parameters

        self.mqtt_host = None
        self.mqtt_user = None
        self.mqtt_pass = None

        self.hass_host = None
        self.hass_token = None
        
        # read config.ini

        try:
            self.config = SnipsConfigParser.read_configuration_file("config.ini")
        except Exception as e:
            print("Failed to read config.ini ({})".format(e))
            self.config = None

        try:
            self.read_toml()
        except Exception as e:
            print("Failed to read /etc/snips.toml ({})".format(e))

        # try to use HASSIO token via environment variable & internal API URL in case no config.ini parameters are given

        if 'hass_token' in self.config['secret']:
            self.hass_token = self.config['secret']['hass_token']
        elif 'HASSIO_TOKEN' in environ:
            self.hass_token = environ['HASSIO_TOKEN']

        if 'hass_host' in self.config['global']:
            self.hass_host = self.config['global']['hass_host']
        elif self.hass_token is not None and 'HASSIO_TOKEN' in environ:
            self.hass_host = 'http://hassio/homeassistant/api'

        self.hass_headers = { 'Content-Type': 'application/json', 'Authorization': "Bearer " + self.hass_token }

        if 'confirmation_success' in self.config['global']:
            self.confirmation_success = self.config['global']['confirmation_success']
        else:
            self.confirmation_success = "Okay"

        if 'confirmation_failure' in self.config['global']:
            self.confirmation_failure = self.config['global']['confirmation_failure']
        else:
            self.confirmation_failure = "Fehler"

        if 'enable_confirmation' in self.config['global'] and self.config['global']['enable_confirmation'] == "True":
            self.enable_confirmation = True

        if self.debug:
            print("Connecting to {}@{} ...".format(self.mqtt_user, self.mqtt_host))

        self.start()

    # -----------------------------------------------------------------------------
    # read_toml

    def read_toml(self):
        snips_config = toml.load('/etc/snips.toml')
    
        if 'mqtt' in snips_config['snips-common'].keys():
            self.mqtt_host = snips_config['snips-common']['mqtt']

        if 'mqtt_username' in snips_config['snips-common'].keys():
            self.mqtt_user = snips_config['snips-common']['mqtt_username']

        if 'mqtt_password' in snips_config['snips-common'].keys():
            self.mqtt_pass = snips_config['snips-common']['mqtt_password']

    # -------------------------------------------------------------------------
    # start

    def start(self):
        with Hermes(mqtt_options = MqttOptions(broker_address = self.mqtt_host, username = self.mqtt_user, password = self.mqtt_pass)) as h:
            h.subscribe_intents(self.on_intent).start()

    # -------------------------------------------------------------------------
    # on_intent

    def on_intent(self, hermes, intent_message):
        intent_name = intent_message.intent.intent_name
        site_id = intent_message.site_id
        room_id = None
        lamp_id = None
        brightness = None

        # extract mandatory information (lamp_id, room_id)

        try:
            if len(intent_message.slots):
                if len(intent_message.slots.lightType):
                    lamp_id = intent_message.slots.lightType.first().value
                    lamp_id = lamp_id.lower().replace('ä', 'ae').replace('ü','ue').replace('ö', 'oe')
                if len(intent_message.slots.roomName):
                    room_id = intent_message.slots.roomName.first().value
                    room_id = room_id.lower().replace('ä', 'ae').replace('ü','ue').replace('ö', 'oe')
                if len(intent_message.slots.brightness):
                    brightness = int(intent_message.slots.brightness.first().value)
        except:
            pass

        # get corresponding home assistant service-url + payload

        service, data = self.params_of(room_id, lamp_id, site_id, brightness, intent_name)

        # fire the service using HA REST API

        if service is not None and data is not None:
            if self.debug:
                print("Intent {}: Firing service [{} -> {}] with [{}]".format(intent_name, self.hass_host, service, data))

            r = requests.post(self.hass_host + service, json = data, headers = self.hass_headers)

            if r.status_code != 200:
                return self.done(hermes, intent_message, r)

            # second additional service? (keep light on = disable automation + turn on light)

            if intent_name == 's710:keepLightOn':
                service, data = self.params_of(room_id, lamp_id, site_id, brightness, "s710:turnOnLight")

                r = requests.post(self.hass_host + service, json = data, headers = self.hass_headers)

            elif intent_name == 's710:keepLightOff':
                service, data = self.params_of(room_id, lamp_id, site_id, brightness, "s710:turnOffLight")

                r = requests.post(self.hass_host + service, json = data, headers = self.hass_headers)

            elif intent_name == 's710:enableAutomatic':
                service, data = self.params_of(room_id, lamp_id, site_id, brightness, "s710:enableAutomaticOff")

                r = requests.post(self.hass_host + service, json = data, headers = self.hass_headers)

            self.done(hermes, intent_message, r)

        else:
          print("Intent {}/parameters not recognized, ignoring".format(intent_name))

    # -------------------------------------------------------------------------
    # done

    def done(self, hermes, intent_message, request_object):
        if not self.enable_confirmation:
            hermes.publish_end_session(intent_message.session_id, "")
        elif request_object.status_code == 200:
            hermes.publish_end_session(intent_message.session_id, self.confirmation_success)
        else:
            hermes.publish_end_session(intent_message.session_id, self.confirmation_failure)

    # -------------------------------------------------------------------------
    # params_of

    def params_of(self, room_id, lamp_id, site_id, brightness, intent_name):

        # turn on/off lights

        if intent_name == 's710:turnOnLight':
            if lamp_id is not None:
                return (HASS_LIGHTS_ON_SVC, {'entity_id': 'light.{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_GROUP_ON_SVC, {'entity_id': 'group.lights_{}'.format(room_id) })
            else:
                return (HASS_GROUP_ON_SVC, {'entity_id': 'group.lights_{}'.format(site_id) })

        if intent_name == 's710:turnOffLight':
            if lamp_id is not None:
                return (HASS_LIGHTS_OFF_SVC, {'entity_id': 'light.{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_GROUP_OFF_SVC, {'entity_id': 'group.lights_{}'.format(room_id) })
            else:
                return (HASS_GROUP_OFF_SVC, {'entity_id': 'group.lights_{}'.format(site_id) })

        # control all lights

        if intent_name == 's710:turnOnAllLights':
            return (HASS_GROUP_ON_SVC, {'entity_id': 'group.all_lights' })

        if intent_name == 's710:turnOffAllLights':
            return (HASS_GROUP_OFF_SVC, {'entity_id': 'group.all_lights' })

        # keep lights on/off (via automation enable/disable + light on/off)

        if intent_name == 's710:keepLightOn':
            if lamp_id is not None:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_off_{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_off_{}'.format(room_id) })
            else:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_off_{}'.format(site_id) })

        if intent_name == 's710:keepLightOff':
            if lamp_id is not None:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_on_{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_on_{}'.format(room_id) })
            else:
                return (HASS_AUTOMATION_OFF_SVC, {'entity_id': 'automation.lights_on_{}'.format(site_id) })

        if intent_name == 's710:enableAutomatic':
            if lamp_id is not None:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_on_{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_on_{}'.format(room_id) })
            else:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_on_{}'.format(site_id) })

        if intent_name == 's710:enableAutomaticOff':
            if lamp_id is not None:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_off_{}'.format(lamp_id) })
            elif room_id is not None:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_off_{}'.format(room_id) })
            else:
                return (HASS_AUTOMATION_ON_SVC, {'entity_id': 'automation.lights_off_{}'.format(site_id) })

        # set light brightness

        if intent_name == 's710:setLightBrightness':
            if lamp_id is not None and brightness is not None:
                return (HASS_LIGHTS_ON_SVC, {'entity_id': 'light.{}'.format(lamp_id), 'brightness': brightness })

        return (None, None)

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    App()
