# Axis Zipstream

Home Assistant Integration für Axis Kameras. Steuert Zipstream und Bildrate
über ein eigenes Stream-Profil, ohne bestehende Kameraeinstellungen zu ändern.

## Getestet mit

- AXIS P3225-LVE Mk II, AXIS OS 9.80.121

Andere Axis Kameras mit VAPIX funktionieren voraussichtlich, sind aber nicht
getestet.

## Was die Integration tut

- Liest beim Einrichten Modell, Seriennummer, `Image.I0.MPEG`, alle
  Stream-Profile und alle installierten ACAP-Anwendungen aus der Kamera.
  Entitäten werden erst danach angelegt.
- Legt ein eigenes Stream-Profil namens `HomeAssistant` an.
- Schreibt Parameteränderungen ausschließlich in dieses Profil.
- Bietet eine Auswahl, welches Stream-Profil live angezeigt wird.

## Was die Integration nicht tut

- Sie schreibt keine globalen Kameraparameter (`Image.I0.MPEG.*`).
- Sie verändert keine fremden Stream-Profile.

Damit bleibt ein parallel laufender Recorder, etwa Synology Surveillance
Station, unberührt.

## Installation

1. Ordner `custom_components/axis_zipstream` nach
   `<config>/custom_components/` kopieren.
2. Home Assistant neu starten.
3. Einstellungen, Geräte & Dienste, Integration hinzufügen, "Axis Zipstream".

## Konfiguration

Beim Einrichten: Host, Benutzername, Passwort, optional Port.

Nachträglich änderbar über "Konfigurieren" am Integrationseintrag:
Auflösung, Bildrate, Komprimierung, Zipstream Stärke, FPS-Modus, GOP-Modus.

Die Auswahlliste für die Zipstream Stärke wird zur Laufzeit aus der Kamera
gelesen (`param.cgi?action=listdefinitions`). Meldet die Kamera nichts,
greift eine Ersatzliste.

## Entitäten

| Entität | Typ | Bedeutung |
| --- | --- | --- |
| `camera.<gerät>` | Camera | Livebild des ausgewählten Profils |
| `select.<gerät>_stream_profil` | Select | Auswahl des Profils für das Livebild |
| `sensor.<gerät>_<app>` | Sensor | Status einer installierten ACAP-Anwendung |
| `select.<gerät>_auflösung` | Select | Auflösung, Liste aus der Kamera gelesen |
| `select.<gerät>_zipstream_stärke` | Select | Zipstream Stärke |
| `select.<gerät>_zipstream_fps_modus` | Select | `fixed` oder `dynamic` |
| `select.<gerät>_zipstream_gop_modus` | Select | `fixed` oder `dynamic` |
| `number.<gerät>_bildrate` | Number | Bildrate 1 bis 30 |
| `number.<gerät>_komprimierung` | Number | Komprimierungsgrad 0 bis 100 |

Alle Einstell-Entitäten schreiben ausschließlich in das Stream-Profil
`HomeAssistant`. Die Auflösungsliste stammt aus
`Properties.Image.Resolution`, die Liste der Zipstream-Stärken aus
`param.cgi?action=listdefinitions`.

Je installierter ACAP-Anwendung wird ein Diagnose-Sensor angelegt. Der Zustand
ist der Status laut Kamera, etwa `Running`. Als Attribute stehen Hersteller,
Version, ApplicationID, Lizenzstatus und die URL der Konfigurationsseite bereit.

Die Abfrage läuft nur, wenn die Kamera
`Properties.EmbeddedDevelopment.Version` 1.20 oder neuer meldet.

## Hinweise

- `videozgopmode=dynamic` kann lange Keyframe-Abstände erzeugen. Manche Player
  kommen damit schlecht zurecht. Voreinstellung ist deshalb `fixed`.
- `videozfpsmode=dynamic` senkt die Bildrate bei wenig Bewegung. In manchen
  Clients kann der Stream dadurch eingefroren wirken.
- Digest-Authentifizierung benötigt aiohttp 3.12 oder neuer.

## Lizenz

GPLv3, siehe LICENSE.
