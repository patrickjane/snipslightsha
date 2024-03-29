# Snips Lights + Homeassistant

App zur Sprachsteuerung von Lampen über Home Assistant (https://www.home-assistant.io/). Nutzt die Home Assistant REST API um Lichter/Lampen ein/auszuschalten, sowie entsprechende Automatisierungen ein/auszuschalten ("Hey Snips, lass das Licht im Flur an"). 

## Installation

#### 1) Home Assistant Access Token anlegen

Im Home Assistant Web-GUI auf das Profil klicken, und dort (siehe auch: https://www.home-assistant.io/docs/authentication/#your-account-profile) unter **Long-Lived Access Tokens** einen Token erstellen. Dieser wird als Konfigurationsparameter für die Snips-App benötigt.

#### 2) Installation der Snips-App

Installation der Lights + Homeassistant App aus dem Store: https://console.snips.ai/store/de/skill_Mb2EmQZ332g

#### 3) Assistant via `sam` installieren/aktualisieren

# Parameter

Die App bentöigt die folgenden Parameter:

- `confirmation_success`: Text der gesprochen wird, nachdem eine Aktion erfolgreich durchgeführt wurde
- `confirmation_failure`: Text der gesprochen wird, nachdem eine Aktion nicht durchgeführt werden konnte
- `enable_confirmation`: TTS Bestätigung aktivieren/deaktivieren
- `hass_host`: Hostname der Home Assistant Installation inkl. Protokoll und Port (z.b. `http://10.0.0.5:8123`)
- `hass_token`: Der Access-Token der in Schritt Installation/1) erstellt wurde

# Funktionen

Die App umfasst folgende Intents:

- `s710:turnOnLight` - Einschalten einer Lichtquelle
- `s710:turnOffLight` - Ausschalten einer Lichtquelle
- `s710:turnOnAllLights` - Einschalten aller Lichtquellen (automatische Home Assistant Gruppe `group.all_lights`) 
- `s710:turnOffAllLights` - Ausschalten aller Lichtquellen (automatische Home Assistant Gruppe `group.all_lights`)
- `s710:keepLightOn` - Einschalten einer Lichtquelle + automatisches Abschalten deaktivieren
- `s710:keepLightOff` - Ausschalten einer Lichtquelle + automatisches Einschalten deaktivieren
- `s710:setLightBrightness` - Einschalten einer Lichtquelle + setzen der Helligkeit
- `s710:enableAutomatic` - Die automatische Steuerung einer Lichtquelle (wieder) aktivieren

Die App kann dabei über 3 Arten angesteuert werden:

- Objektname ("Schalte die *Stehlampe* an)
- Raumname ("Schalte das Licht in der *Küche* an")
- Über Snips `siteID` ("Mach das Licht an")

Letztes funktioniert entsprechend nur, wenn in den gewünschten Räumen Snips-Satelliten installiert und dem entsprechenden Raum zugeordnet sind. Snips erkennt dann, in welchem Raum das Kommando erfolgt, und übermittelt dies als `siteID` an die App, was dort wiederrum als Raumname für die Ansteuerung an Home Assistant verwendet wird.

# Integration Home Assistant

Die App ruft automatisch entsprechende Services auf, um Lichter, Gruppen und Automatisierungen anzusteuern. Da es keine Zuordnung per Konfiguration gibt, müssen in Home Assistant entsprechende Gruppen angelegt werden, bzw. die light-Entities entsprechend benannt werden.

Die Räume und Lampen werden von der App automatisch in Home Assistant Entities übersetzt, und zwar nach folgendem Schema:

1) Bei Nennung von Raum oder ohne Angabe von Raum/Objekt (-> über `siteID`):    
   Entity-ID ist `group.lights_{<RAUM | SITEID>}`
   Service ist `homeassistant.turn_on`/`homeassistant.turn_off`

2) Bei Nennung eines Objekts ("Stehlampe"):    
   Entity-ID ist `light.{<OBJEKT>}`
   Service ist `light.turn_on`/`light.turn_off`
   
3) Für den Intent `s710:keepLightOn`/`s710:keepLightOff` werden Automatisierungen aktiviert/deaktiviert:    
   Entity-ID ist `automation.lights_on_{<RAUM | OBJEKT | SITEID>}"`
   und    
   `automation.lights_off_{<RAUM | OBJEKT | SITEID>}`    
   Service ist `automation.turn_on` / `automation.turn_off`
   
Raumnamen und Objekte werden in Kleinbuchstaben umgewandelt, und Umlaute werden ersetzt (ä -> ae, ü -> ue, ö -> oe).

<img src="example.png" width="490" height="785" />

#### Beispiele

*"Hey Snips, Mach die Stehlampe an"*    
- Intent ist `s710:turnOnLight`
- Objekt ist "Stehlampe"
- -> HA Service ist `light.turn_on`
- -> Payload ist: `{ "entity_id": "light.stehlampe" }` 

*"Hey Snips, Licht aus"*    
- Intent ist `s710:turnOffLight`
- Kein Raum/Objekt genannt, `siteID` wird verwendet, z. B. "Wohnzimmer"
- -> HA Service ist `homeassistant.turn_off`
- -> Payload ist: `{ "entity_id": "group.lights_wohnzimmer" }`

*"Hey Snips, lass das Licht im Schlafzimmer an"*    
- Intent ist: `s710:keepLightOn`
- Raum ist "Schlafzimmer"
- -> HA Service 1 ist `automation.turn_off`
- -> Payload 1 ist: `{ "entity_id": "automation.lights_off_schlafzimmer" }` (Licht nicht mehr automatisch ausmachen)
- -> HA Service 2 ist `homeassistant.turn_on`
- -> Payload 2 ist: `{ "entity_id": "group.lights_wohnzimmer" }` (aber Licht anmachen)
