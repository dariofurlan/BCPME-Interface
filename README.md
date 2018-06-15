# BCPME284S
![Alt text](doc/bcpme%20image.jpeg)
This a little guide with all the things to know to communicate correctly with the Modbus device BCPME284S by Schneider Electric

### Table of Contents

* [Docs](#docs)
* [Install](#install-and-configure)
* [Modbus TCP/IP](#modbus-tcp-ip)
    * [Unit Id](#unit-id)
    * [Function Code](#function-code)
    * [Read Different Data Types](#different-data-types)
        * [Short](#integer-16-bit-(short-signed))
        * [Long](#integer-32-bit-(long-signed))
        * [Float](#float-32-bit-(float))
* [About the Code](#about-the-code)
* [Authors](#authors)

#### Docs:

* [User Guide](https://download.schneider-electric.com/files?p_enDocType=User+guide&p_File_Name=BCPME_user+guide.pdf&p_Doc_Ref=Z206856) - User Guide for the installation of BCPME
* [Register List](https://www.schneider-electric.com/resources/sites/SCHNEIDER_ELECTRIC/content/live/FAQS/212000/FA212184/en_US/BCPMSC_Register_List.pdf) - Register List and How to Read Different Data Types
* [Simply Modbus](http://www.simplymodbus.ca/TCP.htm) - Simple guide with examples to learn about the modbus TCP/IP protocol
* [Modbus Wikipedia](https://en.wikipedia.org/wiki/Modbus) - Wikipedia page about modbus and all different types (useful for function code)

## Install and Configure

There are only few step to install:

<ol>
<li>cd inside the cloned repo and <code style="display:block">pip3.5 install bcpme/</code></li>
<li>change the ip address and port of the influxdb server in "learn_check.py" file (look for the "TODO")</li>
<li>configure the bcpme devices with the connected devices</li>
</ol>

## Modbus TCP-IP

This device communicate with the Modbus protocol over TCP/IP
the modbus request, as you can see int the docs, is built in this precise order:

* **2 bytes** transaction id (`0` in our case)
* **2 bytes** protocol id (`0` in our case)
* **2 bytes** length: the following number of bytes (usually `6` in our case)
* **1 bytes** [unit id](#unit-id): see the section about unit id (`1` or `2` in our case)
* **1 bytes** [function code](#function-code): the function code that tells the action to do (`4` to read, `6` to write)
* **x bytes** data: depends on the function code

### Unit Id

The Modbus device is composed of 4 panels and each one has a number and a letter assigned, we have:

* Panel 1A
* Panel 1B
* Panel 2A
* Panel 2B

each panel has 21 sensors each one numbered physically from 1 to 21, 
but seen from the software perspective **Panel 1A** and  **Panel 1B** ( the same for **Panel 2A** and **Panel 2B**) are just one block that goes from 1 to 42:

* to access Panel 1 (A and B) we use `1` for the "unit id" byte in the modbus request
* to access Panel 2 (A and B) we use `2` for the "unit id" byte in the modbus request

but the number that are written on the panels and the number of registers doesn't always match this is because as you can se at [Page 15 of The User Guide](https://download.schneider-electric.com/files?p_enDocType=User+guide&p_File_Name=BCPME_user+guide.pdf&p_Doc_Ref=Z206856#page=15)
there are 4 types of configuration.

the following table match the physical number with the "virtual" one:

![Alt text](doc/physical_virtual.svg)

To set the type of the configuration you have to write to the register number `6` the corresponding value of the configuration:

* `0` - Top Feed
* `1` - Bottom Feed
* `2` - Sequential
* `3` - Odd / Even

### Function Code

There are around 20 different type of operations supported, we are just intrested in 2

* Read Input Register: (function code:`4`) to read one or more register and the "data" bytes are used as following
    * **2 bytes** number of the first register to read
    * **2 bytes** number of registers to read
* Write Single Holding Register: (function code:`6`) to write one register the "data" bytes are used as following
    * **2 bytes** number of the register to write
    * **2 bytes** the value to write

> little note:
The numbers of the registers in the documentations of the bcpme are augmented by 1 it means that for ex.
to access the register described as number 6 in the docs, we have to use number 5

### Different Data Types
The first page of [the Register List Document](https://www.schneider-electric.com/resources/sites/SCHNEIDER_ELECTRIC/content/live/FAQS/212000/FA212184/en_US/BCPMSC_Register_List.pdf#page=1)
shows how to read all the different data types
#### Integer 16 bit (Short signed)
There are a **value register** and a **scale register** and to obtain the final value:
```python
result = value_16 * pow(10, scale)
```
#### Integer 32 bit (Long signed)
There are **two near value register** and a **scale register** to obtain the final value:
```python
result = value_32 * pow(10, scale)
```
#### Float 32 bit (float)
There are **two near value register** to obtain the final value:
```python
result = value
```
### Multi Phase

In order to access the registers that contains data about multi phase measures you have to enable "user defined status register" number `62017` with `1` 
and if needed assign to the registers starting from `62116` to `62157` and write the val `0` for phase 1,`1` for phase 2,`2` for phase 3 

## About the Code

The BCPME python class handle all the type of wire configurations so there's no need to care about them. 
You can add new device in two ways: 

* From the **physical side**: using the panel number, panel letter and the number physically written on it
* From the **virtual side**: using the unit id and the virtual number

each time a device is added to the BCPME class it saves the map of the devices in json using the physical hierarchy so that it's easy to add devices also editing the json file, but the map of devices in the class uses the virtual hierarchy for convenience.
When Initializing a new BCPME if there's an already saved device with the same name it loads its configuration so when it's initialized once you just need to do ``BCPME("name")``

The file `bcpme_register_map.json` has all the useful registers with the corresponding scale values so there's no need to scroll all the documentation to find the address of you want to read

## Authors

* **Dario Furlan** - *Initial work* - [https://github.com/iofurlan](https://github.com/iofurlan)

## License

Fell free to contribute to this project.
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

