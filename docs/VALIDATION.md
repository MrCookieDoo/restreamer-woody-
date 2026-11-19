# Validatie van de eerste implementatie

De uitbreiding gebruikt de bestaande Restreamer-interface en Core. De
ongewijzigde UI-import staat in een eigen commit; `ui/UPSTREAM.md` vermeldt de
upstream SHA en licentie. De eigen toevoegingen volgen in een afzonderlijke commit.

## Uitgevoerd

- Bestaande UI-productiebuild geslaagd. Volledige UI-suite: 79 tests geslaagd;
  de gerichte Woody-UI-tests zijn na UI-aanpassingen opnieuw geslaagd. CI herhaalt
  de volledige suite en build op de definitieve branch.
- Backend en daadwerkelijke GStreamer-mixer: 25 tests, waaronder 13 gelijktijdige
  bronnen, 100 wissels, echte pixelcontrole en PCM-stilte na verbergen, behoud
  van blokkeringen bij herimport, een vastgelopen camera en uitgangsherstel.
- Chatbot: TypeScript-controle en tests geslaagd voor rollen, het negeren van
  oude berichten en dezelfde commandoroute voor beide platforms.
- Compose-configuratie gecontroleerd, inclusief geldige GHCR-imagenamen voor de
  fork waarvan de GitHub-naam op een koppelteken eindigt.
- Integratie met de officiële bestaande Core 16.16.0-binary: dezelfde Core-login
  werkt ook voor Studio; het hoofdkanaal wordt zonder duplicaten aangemaakt.
- Daadwerkelijke HLS-uitgang gedecodeerd als H.264, 1920×1080, aangegeven
  framefrequentie 25/1, en AAC, 48 kHz stereo. De gecodeerde proef gebruikte
  13 synthetische bronnen en 100 wissels. De mixer had na circa negen minuten
  geen uitgangsherstart; verbergen schakelde de geselecteerde audio uit.

## Praktische grenzen

De cloudworkspace heeft 8 GB schijfruimte en gebruikt Docker met VFS. Daardoor
kon de volledige productie-bundelbuild hier niet worden afgerond. De Ubuntu
24.04/GStreamer 1.24-mediabibliotheken zijn wel daadwerkelijk gebouwd en getest.
De ontbrekende Pango-plugin en runtime-bestandsrechten zijn in de
productie-Dockerfiles gecorrigeerd.

De lokale Core-integratie gebruikte de officiële Core-binary met host-FFmpeg
7.1.5. Die mist de datarhei-progresspatches; uitsluitend in deze lokale proef is
de stale-watchdog van het hoofdkanaal uitgeschakeld. De productie-Dockerfile
behoudt de officiële, gepatchte FFmpeg 6.1.1-image en de normale watchdog. De
volledige gepinde combinatie moet via CI of de doelserver worden gebouwd en
gecontroleerd voordat bestaande uitzendingen worden overgezet.

De aangegeven HLS-framefrequentie is geen capaciteitsgarantie voor de doelhardware.
Werkelijke cameramodellen, GPU-versnelling, Twitch-/YouTube-accountkoppelingen en
de 24-uursduurtest zijn nog niet op locatie uitgevoerd. Zie `TESTING.md` voor
acceptatie en `INSTALL.md` voor installatie, back-up en terugzetten.
