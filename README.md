# NayerControl

**NayerControl** es una aplicación de escritorio para Windows que permite controlar y reflejar la pantalla de un celular Android desde la PC, por cable USB o de forma completamente inalámbrica (Wi-Fi), sin necesidad de usar la terminal ni conocer comandos de Android.

No es un motor de reflejo propio: es una interfaz gráfica en español, pensada para usuarios no técnicos, construida **sobre** las herramientas oficiales de Android para depuración y reflejo de pantalla.

---

## Índice

- [¿Qué hace la app?](#qué-hace-la-app)
- [Motores y tecnologías que usa](#motores-y-tecnologías-que-usa)
- [Arquitectura del proyecto](#arquitectura-del-proyecto)
- [Funcionalidades](#funcionalidades)
- [Requisitos](#requisitos)
- [Instalación y uso](#instalación-y-uso)
- [Ejecutar desde el código fuente](#ejecutar-desde-el-código-fuente)
- [Compilar el ejecutable (.exe)](#compilar-el-ejecutable-exe)
- [Dónde se guarda la configuración](#dónde-se-guarda-la-configuración)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Licencias y créditos](#licencias-y-créditos)

---

## ¿Qué hace la app?

- Refleja la pantalla del celular en una ventana de la PC y permite controlarlo con mouse/teclado, como si fuera un emulador.
- Soporta dos modos de conexión:
  - **USB (cable)**: conecta el celular, activa "Depuración USB" y listo.
  - **Wi-Fi (inalámbrico)**: controla el celular sin cable, en la misma red Wi-Fi.
- Guarda los celulares ya emparejados para reconectarlos con un clic la próxima vez.
- Detecta el celular automáticamente en la red (sin que el usuario tenga que copiar direcciones IP a mano) una vez que fue emparejado al menos una vez.
- Ajusta automáticamente la calidad de video (bitrate, resolución, fps, audio) para que el reflejo por Wi-Fi vaya fluido, ya que el Wi-Fi tiene menos ancho de banda y más latencia que el USB.
- Todo con mensajes de error y avisos en español, orientados a alguien que nunca usó `adb` ni `scrcpy` por línea de comandos.

## Motores y tecnologías que usa

NayerControl **no reinventa el reflejo de pantalla**: usa las mismas herramientas oficiales que usan los desarrolladores de Android, empaquetadas dentro de la app, y les pone una interfaz gráfica encima.

| Componente | Rol | Origen / licencia |
|---|---|---|
| **[scrcpy](https://github.com/Genymobile/scrcpy)** | Motor real de reflejo y control de pantalla (captura de video, envío de eventos de mouse/teclado al celular). Es el `.exe` que efectivamente abre la ventana donde se ve el celular. | Genymobile — GPL-3.0 |
| **ADB (Android Debug Bridge)** | Herramienta de Android para detectar dispositivos, emparejar por Wi-Fi, y establecer la conexión que scrcpy usa para hablar con el celular. | Android Open Source Project (Google) — Apache License 2.0 |
| **Python 3** | Lenguaje en el que está escrita toda la capa de aplicación (todo lo que no es scrcpy/adb). | PSF License |
| **[PySide6](https://doc.qt.io/qtforpython/) (Qt for Python)** | Framework de interfaz gráfica: ventanas, botones, diálogos, hilos de trabajo en segundo plano. | Qt Company — LGPL-3.0 |
| **[PyInstaller](https://pyinstaller.org/)** | Empaqueta la app de Python en un `.exe` independiente que no requiere tener Python instalado. | PyInstaller — GPL con excepción de empaquetado |
| **[Inno Setup](https://jrsoftware.org/isinfo.php)** | Genera el instalador de Windows (`installer/setup.iss`). | Jordan Russell — Freeware |

En resumen: **scrcpy + adb hacen todo el trabajo pesado** (video, input, protocolo de Android); NayerControl es la capa de Python/Qt que simplifica conectarlos, emparejarlos y configurarlos sin usar la terminal.

## Arquitectura del proyecto

```
NayerControl/
├── app/
│   ├── main.py                    # Punto de entrada: crea la QApplication y la ventana principal
│   ├── config.py                  # Config persistente en %APPDATA%\NayerControl\config.json
│   ├── device_manager.py          # Capa que invoca adb.exe/scrcpy.exe (subprocess)
│   └── ui/
│       ├── main_window.py         # Ventana principal (pestañas USB / Wi-Fi, bandeja del sistema)
│       ├── wireless_pairing_dialog.py  # Emparejamiento por Depuración inalámbrica + actualizar dirección
│       ├── settings_dialog.py     # Ajustes de video (calidad, resolución, optimización Wi-Fi)
│       └── workers.py             # Hilo QThread genérico para no bloquear la UI
├── resources/
│   ├── icon.ico                   # Ícono de la app (ventana, bandeja, instalador)
│   └── bin/                       # Binarios oficiales de scrcpy y adb (sin modificar)
├── installer/setup.iss            # Script de Inno Setup para el instalador de Windows
├── build_nayercontrol.spec        # Configuración de PyInstaller
└── requirements.txt
```

## Funcionalidades

### Modo USB
Conecta el cable, activa "Depuración USB" en Opciones de desarrollador, la app detecta el celular automáticamente y listo — sin configuración adicional.

### Modo Wi-Fi (Depuración inalámbrica)
Usa la función nativa de Android 11+ ("Depuración inalámbrica"), **no** el truco antiguo de `adb tcpip` — ese método ata la conexión Wi-Fi a la sesión de depuración USB y se corta al desconectar el cable en muchos celulares. El emparejamiento nativo es independiente del cable desde el principio:

1. **Emparejar celular nuevo**: se pide la IP:puerto de emparejamiento y el código de 6 dígitos que muestra el celular (sin cable, nunca).
2. **Reconectar / Iniciar control remoto**: intenta encontrar el celular solo en la red (mDNS) antes de usar la última dirección guardada, porque el puerto de Depuración inalámbrica puede cambiar con el tiempo.
3. **Actualizar dirección de conexión**: respaldo manual para cuando la detección automática no encuentra el celular (redes que bloquean mDNS, etc.).

### Optimización automática para Wi-Fi
Al conectar por Wi-Fi, la app aplica automáticamente un bitrate menor, resolución tope, límite de fps y desactiva audio (todo configurable), para compensar el menor ancho de banda de Wi-Fi frente a USB y evitar lag. Se puede desactivar desde Ajustes de video.

### Otros
- Ícono en la bandeja del sistema.
- Panel de estado/log con los mensajes de cada acción.
- Recuerda el último celular usado y el modo de conexión preferido.

## Requisitos

- Windows 10/11 (64 bits).
- Un celular Android con "Opciones de desarrollador" activadas.
- Para el modo Wi-Fi: Android 11 o superior (Depuración inalámbrica), y el celular en la misma red Wi-Fi que la PC.

## Instalación y uso

La forma más simple es descargar/compilar el `.exe` (ver más abajo) y ejecutarlo — no requiere instalar Python ni ninguna dependencia, ya que todo viene empaquetado.

## Ejecutar desde el código fuente

```bash
pip install -r requirements.txt
python app/main.py
```

## Compilar el ejecutable (.exe)

```bash
pip install -r requirements.txt
python -m PyInstaller build_nayercontrol.spec --noconfirm
```

El resultado queda en `dist/NayerControl/NayerControl.exe` (junto a su carpeta `_internal` con las dependencias — ambas cosas deben moverse juntas).

Para generar el instalador de Windows (`NayerControl-Setup-*.exe`), con [Inno Setup](https://jrsoftware.org/isinfo.php) instalado, compila `installer/setup.iss`.

## Dónde se guarda la configuración

`%APPDATA%\NayerControl\config.json` — celulares emparejados, modo de conexión preferido y ajustes de video. Se puede borrar sin problema para reiniciar la configuración desde cero.

## Limitaciones conocidas

- Algunos celulares (se observó en modelos Huawei/Honor) desactivan "Depuración USB" al activar "Depuración inalámbrica", o muestran en pantalla un puerto de conexión que no se actualiza hasta apagar y prender el interruptor. Es un comportamiento del propio Android/fabricante, no de la app; por eso existe la detección automática por red y el botón de actualizar dirección como respaldo.
- La detección automática por red (mDNS) depende de que el router no bloquee tráfico multicast entre dispositivos; en redes que sí lo bloquean, hay que usar la actualización manual de dirección.
- Solo probado en Windows.

## Licencias y créditos

Este proyecto empaqueta y usa, sin modificar:

- **[scrcpy](https://github.com/Genymobile/scrcpy)**, de Genymobile, bajo licencia **GPL-3.0**.
- **adb**, parte de [Android Open Source Project](https://source.android.com/), bajo licencia **Apache-2.0**.

El código propio de NayerControl (la interfaz en `app/`) es la capa que simplifica el uso de esas herramientas. Al distribuir este proyecto se debe respetar la licencia GPL-3.0 de scrcpy: el código fuente debe estar disponible y no se puede restringir la libre redistribución del programa.
