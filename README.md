# Nibe - TecoAPI integration for Home Assistant

## Installation

### Manual installation

1. Download the zip file and extract to your "custom_components" folder. (Create the "custom_components" folder is it does not exist.)
2. Rename the folder "hass_tecoapi-master" to "tecoapi". All files should be inside the "tecoapi" folder under the custom_components folder.

## Setup

1. Add tecoapi configuration block to your `<config dir>/configuration.yaml`
2. Restart your Home assistant to make changes take effect.

```yaml
tecoapi:
    resource: http://<<IP or Domain Name>>/TecoApi/
    username: <<username>>
    password: <<password>>
    getinfo: true
    getlist: true
```

## Configuration

ST {PUBLIC_API} objects:

```ST
TYPE
  TRooms : STRUCT
    R1 : BOOL;
    R2 : BOOL;
  END_STRUCT;
END_TYPE

TYPE
  TFloors : STRUCT
    FirstFloor : TRooms;
    SecondFloor : TRooms;
  END_STRUCT;
END_TYPE


VAR_GLOBAL
  Lights {PUBLIC_API} : TFloors;
  Windows {PUBLIC_API} : TFloors;
END_VAR


VAR_GLOBAL
  HotWater {PUBLIC_API} : REAL;
END_VAR
```

Example 1:

```yaml
tecoapi:
    resource: http://<<IP or Domain Name>>/TecoApi/
    username: <<username>>
    password: <<password>>
    switches:
      - object: Lights
        name: Lights
        subobjects:
          - object: FirstFloor
            name: First floor
            subobjects:
              - object: R1
                name: Living Room
              - object: R2
                name: Kitchen
    binary_sensors:
      - object: Windows.FirstFloor.R1
        name: Kitchen Window
        device_class: window
    sensors:
      - object: HotWater
        name: Hot water temperature
        unit_of_measurement: °C
```

Example 1:

```yaml
tecoapi:
    resource: http://<<IP or Domain Name>>/TecoApi/
    username: <<username>>
    password: <<password>>

switch:
  - platform: tecoapi
    object: Lights
    name: Lights
    subobjects:
      - object: FirstFloor
        name: First floor
        subobjects:
          - object: R1
            name: Living Room
          - object: R2
            name: Kitchen

binary_sensor:
  - platform: tecoapi
    object: Windows.FirstFloor.R1
    name: Kitchen Window
    device_class: window

sensor:
  - platform: tecoapi
    object: HotWater
    unit_of_measurement: °C
```
